from fastapi import FastAPI, Request, Header, Response, Form, Depends, BackgroundTasks, HTTPException
from app.db import get_db
from sqlmodel import Session
from app.crud import update_oauth_code, get_posts_for_member, get_posts_public, get_actor_or_create
from app.mastodonapi import confirm_actor_valid
import asyncio
from app.common import get_config, is_valid_group_name
from nicegui import Client, ui
from typing import Dict, Any
from PIL import Image
import hashlib
import io
import os
import json
import copy


config = get_config()
SERVER_DOMAIN = config["main"]["server_url"]
UPLOAD_FOLDER = config["main"]["upload_folder"]
SERVER_URL = "https://" + SERVER_DOMAIN

COLOR_THEME_LIGHT = {
    "time_text": "#A6A6A6",
    "icon_color": "#5898D4",
    "post_color": "black",
    "color_border": "black",
    "color_box": "white"
}

def get_comments_tree(comments) -> Dict[str, Any]:
    """Build a dict tree of a post and its comments

    Args:
        comments (Boost): A boost class

    Returns:
        Dict[str, Any]: A dict containging the data for the node and its children with the same data
    """
    comment_root = {"comments": []}
    stack = [(comments, comment_root)]

    while len(stack) > 0:
        node, comment_dict = stack.pop()

        comment_dict["data"] = {
            "profile_src": node.original_poster.profile_picture,
            "id": node.note_id,
            "profile_name": node.original_poster.name,

            "group_src": node.attributed.profile_picture,
            "group_name": node.group.name,

            "post": node.content,
            "created_at": node.original_time.strftime("%m/%d/%Y, %H:%M:%S"),
        }
        comment_dict["comments"] = []

        for child in node.comments:
            child_dict = {}
            stack.append((child, child_dict))
            comment_dict["comments"].append(child_dict)
    return comment_root

def get_avatar(db, actor_handle):
    actor = get_actor_or_create(db, actor_handle)
    return actor.profile_picture


def switch_tab(msg: Dict) -> None:
    #TODO FIX SCOPE
    name = msg['args']
    # tabs.props(f'model-value={name}')
    # panels.props(f'model-value={name}')


def avatar(src, style="", size=32):
    ui.image(src).style(f'border-radius: 50%; height: {size}px; width: {size}px;' + style)

def div(ui):
    return ui.element('div')

def resize_image_profile(data, width, height):
    image_file = io.BytesIO(data)

    with Image.open(image_file) as image:
        origin_width, origin_height = image.size
        origin_format = image.format

        new_width, new_height = origin_width, origin_height
        # Resize image
        if origin_width > width or origin_height > height:
            if width > height:
                left = (width - height) / 2
                upper = 0
                right = (width + height) / 2
                lower = height
            else:
                left = 0
                upper = (height - width) / 2
                right = width
                lower = (height + width) / 2
            image = image.crop((left, upper, right, lower))
            image = image.resize((width, height))

            new_width, new_height = image.size
            image_file.seek(0)


        # Save image
        readable_hash = hashlib.sha256(data).hexdigest()
        save_format = "jpg"
        if origin_format == "PNG":
            save_format = "png"
        elif origin_format == "GIF":
            save_format = "gif"
        saved_name = f"{readable_hash}_{new_width}_{new_height}.{save_format}"
        save_url = f"/uploads/{saved_name}"
        save_path = os.path.join(UPLOAD_FOLDER, saved_name)
        if not os.path.isfile(save_path):
            image.save(save_path)

        return save_url


def post_card(ui, post_tree, color_theme):
    post_dict = post_tree["data"]
    profile_src = post_dict["profile_src"]
    profile_name = post_dict["profile_name"]
    created_at = post_dict["created_at"]
    post = post_dict["post"]
    post_id = post_dict["id"]
    comments = post_tree["comments"]

    group_src = post_dict["group_src"]
    group_name = post_dict["group_name"]
    

    time_text = color_theme["time_text"]
    icon_color = color_theme["icon_color"]
    post_color = color_theme["post_color"]
    color_border = color_theme["color_border"]
    color_box = color_theme["color_box"]
    def set_hightlight(element):
        element.style(f'color: #9CBEDE;')

    def set_back(element):
        element.style(f'color: {icon_color};')

    with ui.element('div').style(f'background-color: {color_box}; border: 1px solid {color_border}; box-shadow: '
                        f'none; color: {icon_color}; padding: 32px; border-radius: 8px;'):
        # profile avatar
        with ui.row().classes('flex items-center'):
            ui.image(profile_src).classes('rounded-full h-8 w-8')
            ui.label(profile_name).classes(f'{post_color} text-base font-light')

            # Group to arrow
            to_group = ui.icon('chevron_right').classes('text-sm')
            
            # Group avatar
            ui.image(group_src).classes('rounded-full h-8 w-8')
            ui.label(group_name).classes(f'{post_color} text-base font-light')


        # post
        with ui.row().classes('mt-4'):
            ui.html(post).classes('text-base font-light').style(f'color: {post_color};')

        # date, share, like
        with ui.row().classes('flex justify-between items-center w-full mt-4'):
            ui.label(created_at).classes('text-xs font-light').style(f'color: {time_text};')

            def like_post(post_id):
                print(post_id)
                
            with div(ui):
                share = ui.icon('share').classes('mr-4 text-sm').on("mouseover", lambda:  set_hightlight(share)).on("mouseout", lambda: set_back(share))
                tumbs_up = ui.icon('thumb_up').classes('text-sm').on("mouseover", lambda:  set_hightlight(tumbs_up)).on("mouseout", lambda: set_back(tumbs_up)).on("click", lambda: like_post(post_id))
                

        # divider
        with ui.row().classes('w-full mt-8 mb-8'):
            div(ui).classes('w-full h-px').style(f'background-color: {color_border}')

            stack = []
            with ui.expansion('Comments').classes('text-xs font-light') as expansion:
                for comment in comments:
                    stack.append((comment, 0, expansion))
                while len(stack) >  0:
                    node, level, expansion = stack.pop()
                    with ui.row().classes('w-full'):
                        with expansion:
                            padding = level*10

                            with ui.row().classes('flex items-center').style(f'padding-left: {padding}px; padding-bottom: 3px;'): # f"border: 1px solid #4CAF50;"):
                                avatar(node["data"]["profile_src"], "", 16)
                                ui.label(node["data"]["profile_name"]).classes(f'{post_color}')
                                ui.html(f'{node["data"]["post"]}')
                            expansion_child = div(ui)#  ui.expansion('More').classes('text-xs font-light')
                            for comment in node["comments"]:
                                stack.append((comment, level + 1, expansion_child))
                    

        # # retweet
        # with ui.row().classes('flex items-center mt-6'):
        #     avatar(src='images/cat5.png')
        #     ui.label("Retweeter").classes(f'text-sm {post_color}')

        # with ui.row().classes('mt-4'):
        #     ui.label(boost).classes('text-xs font-light').style(f'color: {post_color}')

        # with ui.row().classes('w-full mt-8'):
        #     with ui.element("div").classes('flex w-full justify-center items-center rounded-full p-2').style(
        #             f'border: 1px solid {color_border}; box-shadow: none; background-color: {color_box};'):
        #         ui.label("Show all").classes(f'mr-4 text-xs {post_color}')
        #         # ui.icon('expand_more').classes(f'{post_color}')




async def get_username(ui):
    username_data = await ui.run_javascript(
        f"""
        var xmlhttp = new XMLHttpRequest();
        xmlhttp.open("GET", "/get_username", false);
        xmlhttp.send();
        (JSON.parse(xmlhttp.responseText));
        """
        )
    return username_data.get("username")

async def send_logout(ui):
    logout_data = await ui.run_javascript(
        f"""
        var xmlhttp = new XMLHttpRequest();
        xmlhttp.open("GET", "/logout", false);
        xmlhttp.send();
        (JSON.parse(xmlhttp.responseText));
        """
        )
    return logout_data

async def send_refresh(ui):
    logout_data = await ui.run_javascript(
        f"""
        var xmlhttp = new XMLHttpRequest();
        xmlhttp.open("GET", "/refresh", false);
        xmlhttp.send();
        (JSON.parse(xmlhttp.responseText));
        """
        )
    return logout_data

async def is_authenticated(ui) -> bool:
    username = await get_username(ui)
    return username is not None

def init(app: FastAPI) -> None:
    @ui.page('/')
    async def show(request: Request, client: Client, db: Session = Depends(get_db)):
        # Wait for page to load
        await asyncio.sleep(2)
        try:
            await client.connected()
        except TimeoutError:
            await asyncio.sleep(1)
            await client.connected()
        await asyncio.sleep(2)
        
        with ui.header().classes(replace='row items-center') as header:
            ui.button(on_click=lambda: left_drawer.toggle()).props('flat color=white icon=menu')
            with ui.tabs() as tabs:
                ui.tab('Home', icon='home')
                ui.tab('All', icon='public')
                ui.tab('About', icon='info')


        # with ui.footer(value=False) as footer:
        #     ui.label('Footer')

        with ui.left_drawer().classes('bg-blue-100') as left_drawer:
            # ui.label()
            
            with ui.expansion().classes('text-xs font-light') as expansion:
                with expansion.add_slot('header'):
                    if await is_authenticated(ui):
                        username = await get_username(ui)
                        avatar_url = get_avatar(db, username)
                        avatar(avatar_url, "", 16)
                        ui.label(f'{username}').style("padding-left: 5px")

                async def submit_new_group():
                    request_data = {
                        "group_name": group_name.value,
                        "display_name": display_name.value,
                        "description": description.value,
                        "profile_picture": profile_picture.save_url,
                        "cover_photo": cover_photo.save_url,
                        "creator_handle": username,
                    }
                    payload = json.dumps(request_data)

                    response = await ui.run_javascript(
                    f"""
                    var data = JSON.parse('{payload}');
                    var xmlhttp = new XMLHttpRequest();

                    var params = new URLSearchParams();
                    for (var key in data) {{
                        if (data.hasOwnProperty(key)) {{
                        params.append(key, data[key]);
                        }}
                    }}
                    xmlhttp.open("POST", "/create_group_post?" + params.toString(), false);
                    xmlhttp.send();
                    var return_value = xmlhttp.responseText;
                    try {{
                        return_value = JSON.parse(xmlhttp.responseText);
                    }} catch (e) {{
                        return_value = xmlhttp.responseText;
                    }}
                    (xmlhttp.responseText)
                    """,
                        respond=True,
                    )
                    try:
                        response = json.loads(response)
                    except JSONDecodeError:
                        pass
                    if type(response) == dict:
                        if response["success"]:
                            print(f"group created: {group_name.value}")
                            await ui.run_javascript(f'window.location.replace("/group/{group_name.value}");',respond=False)
                            ui.notify(f'Group created, redirecting to group page')
                        else:
                            # Handle group creation error
                            if "message" in response.keys():
                                ui.notify(f'Group not created: {response["message"]}')
                            else:
                                ui.notify(f'Group not created: {response}')
                    else:
                        ui.notify(f'Response not readable data: {response}')

                
                with ui.column():
                    with ui.row():
                        ui.icon('logout')
                        ui.link('Logout', "/ui_logout")

                    with ui.dialog().props('persistent fullWidth fullHeight') as dialog, ui.card():
                        with ui.element('q-toolbar-title'):
                            with ui.row():
                                ui.icon('group_add')
                                ui.label('Create New Group')
                                ui.icon('close').props("v-close-popup").classes("on-right flat round dense cursor-pointer absolute-right").on("click", dialog.close)

                        with ui.column().classes('items-center'):
                            group_name = ui.input(label="Group name", placeholder='cats',
                            validation={
                                'Input too short': lambda value: len(value) > 1,
                                "only use alphanumeric letters (letters, numbers, underscores, hyphens)": is_valid_group_name
                                }
                            )
                            display_name = ui.input(label="Display name", placeholder='The cute cat group',
                            validation={'Input too short': lambda value: len(value) > 1}
                            )
                            description = ui.textarea(label="Description", placeholder='This group is a place to exchange picture of cats',
                            validation={'Input too short': lambda value: len(value) > 1}
                            )

                            def handle_upload_profile(event, element, width=400, height=400):
                                with event.content as f:
                                    data = f.read() # read entire file as bytes
                                    save_url = resize_image_profile(data, width, height)
                                    
                                    element.save_url = save_url
                                    ui.notify(f'Uploaded {element.save_url}')



                            profile_picture = ui.upload(auto_upload=True, on_upload=lambda e:  handle_upload_profile(e, profile_picture), label="Profile picture", max_files=1).props('accept=".jpg, image/*"')
                            profile_picture.save_url = None
                            cover_photo = ui.upload(auto_upload=True, on_upload=lambda e: handle_upload_profile(e, cover_photo, 1920, 1080), label="Cover picture", max_files=1)
                            cover_photo.save_url = None
                            ui.button('Create', on_click=submit_new_group)

                            # with ui.row():
                            #     ui.button('Close', on_click=dialog.close)
                            #     ui.button('Create', on_click=submit_new_group)
                    with ui.row():
                        ui.icon('group_add')
                        ui.link("Create new group").on("click", dialog.open)
                
            
        # start closed if logged out
        if not await is_authenticated(ui):
            left_drawer.toggle()

        with ui.tab_panels(tabs, value='Home'):
            if await is_authenticated(ui):
                with ui.tab_panel("Home").style('border-radius: 50%; height: 800px; width: 640px;'):
                    for post_db in get_posts_for_member(db, await get_username(ui)):
                        comments = []
                        comments_tree = get_comments_tree(post_db)
                        post_card(ui, comments_tree, COLOR_THEME_LIGHT)

                with ui.tab_panel("All").style('border-radius: 50%; height: 800px; width: 640px;'):
                    for post_db in get_posts_public(db, await get_username(ui)):
                        comments = []
                        comments_tree = get_comments_tree(post_db)
                        post_card(ui, comments_tree, COLOR_THEME_LIGHT)
            else:
                with ui.tab_panel("Home").style('border-radius: 50%; height: 800px; width: 640px;'):
                    ui.link('Click to login', "/ui_login").style('color: #6E93D6; font-size: 200%; font-weight: 300')

                with ui.tab_panel("All").style('border-radius: 50%; height: 800px; width: 640px;'):
                    ui.link('Click to login', "/ui_login").style('color: #6E93D6; font-size: 200%; font-weight: 300')

                
            with ui.tab_panel('About'):
                ui.label('This is the second tab')


    @ui.page('/oauth_login_code_frontend')
    async def oauth_login_code_frontend(request: Request, client: Client, code: str, state: str, db: Session = Depends(get_db)) -> None:
        ui.label('Logging you in, please wait')
        # Wait for page to load
        await asyncio.sleep(2)
        await client.connected()
        await asyncio.sleep(2)
        # await ui.run_javascript("alert('yay');")
        
        await ui.run_javascript(
            f"""
            var xhttp = new XMLHttpRequest();
            xhttp.getResponseHeader('Set-Cookie');
            xhttp.withCredentials = true;
            xhttp.open("GET", "/oauth_login_code?state={state}&code={code}", true);
            xhttp.setRequestHeader('Content-type', 'application/x-www-form-urlencoded');
            xhttp.onreadystatechange = function() {{

                if (xhttp.readyState == XMLHttpRequest.DONE) {{
                    // alert(xhttp.responseText);
                    window.location.replace("/");

                }}
                
            }};
            xhttp.send();
            """,
                respond=False,
            )
        ui.label('Logged in, prepare for redirect')
        

    @ui.page('/ui_login')
    def login(request: Request) -> None:
        async def try_login() -> None:  # local function to avoid passing username and password as arguments
            await ui.run_javascript(
            f"""
            const form = document.createElement('form');
            form.method = 'post';
            form.action = '/oauth_login_submit';

            const username_field = document.createElement('input');
            username_field.type = 'hidden';
            username_field.name = 'username';
            username_field.value = '{username.value}';
            form.appendChild(username_field);

            const login_type_field = document.createElement('input');
            login_type_field.type = 'hidden';
            login_type_field.name = 'login_type';
            login_type_field.value = 'frontend';
            form.appendChild(login_type_field);

            document.body.appendChild(form);
            form.submit();
            """,
                respond=False,
            )

        # if is_authenticated(ui):
        #     return ui.open('/')

        # request.session['id'] = str(uuid.uuid4())  # NOTE this stores a new session ID in the cookie of the client
        with ui.card().classes('absolute-center'):
            username = ui.input('Username').on('keydown.enter', try_login)
            ui.button('Log in', on_click=try_login)
            ui.label(ui.open('/protected'))


    @ui.page('/ui_logout')
    async def logout_page(request: Request, client: Client) -> None :
        # Wait for page to load
        await asyncio.sleep(2)
        await client.connected()
        await asyncio.sleep(2)
        refresh_data = await send_refresh(ui)
        await asyncio.sleep(2)
        logout_data = await send_logout(ui)
        await ui.run_javascript(
            f"""
            window.location.replace("/");
            """,
                respond=False,
        )
        ui.label('Logged out, prepare for redirect back to main page')

    ui.run_with(app, title="Fedigroup", favicon="app/static/default_group_icon.png")