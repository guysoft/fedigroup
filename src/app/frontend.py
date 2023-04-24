from fastapi import FastAPI, Request, Header, Response, Form, Depends, BackgroundTasks, HTTPException
from app.db import get_db
from sqlmodel import Session
from app.crud import update_oauth_code, get_posts_for_member
from app.mastodonapi import confirm_actor_valid
import asyncio
from app.common import get_config
from nicegui import Client, ui
from typing import Dict

config = get_config()
SERVER_DOMAIN = config["main"]["server_url"]
SERVER_URL = "https://" + SERVER_DOMAIN

COLOR_THEME_LIGHT = {
    "time_text": "#A6A6A6",
    "icon_color": "#5898D4",
    "post_color": "black",
    "color_border": "black",
    "color_box": "white"
}

def switch_tab(msg: Dict) -> None:
    #TODO FIX SCOPE
    name = msg['args']
    # tabs.props(f'model-value={name}')
    # panels.props(f'model-value={name}')


def avatar(src, style=""):
    ui.image(src).style('border-radius: 50%; height: 32px; width: 32px;' + style)
def div(ui):
    return ui.element('div')

def post_card(ui, post_dict, color_theme):
    profile_src = post_dict["profile_src"]
    profile_name = post_dict["profile_name"]
    created_at = post_dict["created_at"]
    post = post_dict["post"]
    

    time_text = color_theme["time_text"]
    icon_color = color_theme["icon_color"]
    post_color = color_theme["post_color"]
    color_border = color_theme["color_border"]
    color_box = color_theme["color_box"]
    # boost="Boost!"

    with ui.element('div').style(f'background-color: {color_box}; border: 1px solid {color_border}; box-shadow: '
                        f'none; color: {icon_color}; padding: 32px; border-radius: 8px;'):
        # profile avatar
        with ui.row().classes('flex items-center'):
            ui.image(profile_src).classes('rounded-full h-8 w-8')
            ui.label(profile_name).classes(f'{post_color} text-base font-light')

        # post
        with ui.row().classes('mt-4'):
            ui.html(post).classes('text-base font-light').style(f'color: {post_color};')

        # date, share, like
        with ui.row().classes('flex justify-between items-center w-full mt-4'):
            ui.label(created_at).classes('text-xs font-light').style(f'color: {time_text};')
            with div(ui):
                ui.icon('share').classes('mr-4 text-sm')
                ui.icon('thumb_up').classes('text-sm')

        # divider
        with ui.row().classes('w-full mt-8 mb-8'):
            div(ui).classes('w-full h-px').style(f'background-color: {color_border}')

        # # retweet profiles
        # with ui.row().classes('flex justify-between items-center w-full'):
        #     with div(ui):
        #         avatar(src='images/cat1.png', style='z-index: 3;')
        #         avatar(src='images/cat2.png', style='margin-left: -16px; z-index: 2;')
        #         avatar(src='images/cat3.png', style='margin-left: -16px; z-index: 1;')
        #         avatar(src='images/cat4.png', style='margin-left: -16px; z-index: 0;')

            with div(ui):
                ui.label("Comments").classes('text-xs font-light')

        # # retweet
        # with ui.row().classes('flex items-center mt-6'):
        #     avatar(src='images/cat5.png')
        #     ui.label("Retweeter").classes(f'text-sm {post_color}')

        # with ui.row().classes('mt-4'):
        #     ui.label(boost).classes('text-xs font-light').style(f'color: {post_color}')

        with ui.row().classes('w-full mt-8'):
            with ui.element("div").classes('flex w-full justify-center items-center rounded-full p-2').style(
                    f'border: 1px solid {color_border}; box-shadow: none; background-color: {color_box};'):
                ui.label("Show all").classes(f'mr-4 text-xs {post_color}')
                # ui.icon('expand_more').classes(f'{post_color}')




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

def is_authenticated(ui) -> bool:
    return get_username(ui) is not None

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
        

        # username = await ui.run_javascript('Date()')
        
        with ui.header().classes(replace='row items-center') as header:
            ui.button(on_click=lambda: left_drawer.toggle()).props('flat color=white icon=menu')
            with ui.tabs() as tabs:
                ui.tab('Home', icon='home')
                ui.tab('All', icon='public')
                ui.tab('About', icon='info')


        # with ui.footer(value=False) as footer:
        #     ui.label('Footer')

        with ui.left_drawer().classes('bg-blue-100') as left_drawer:
            ui.label(f'Login: {await get_username(ui)}')
        # start closed
        # left_drawer.toggle()
        color_profile = {

        }
        with ui.tab_panels(tabs, value='Home'):

            with ui.tab_panel("Home").style('border-radius: 50%; height: 800px; width: 640px;'):
                for post_db in get_posts_for_member(db, await get_username(ui)):
                    post = {
                        "profile_src": post_db.original_poster.profile_picture,
                        "profile_name": post_db.original_poster.name,
                        "post": post_db.content,
                        "created_at": post_db.original_time.strftime("%m/%d/%Y, %H:%M:%S"),
                    }

                    post_card(ui, post, COLOR_THEME_LIGHT)
                    
                # post_card(ui, profile_src=SERVER_URL + "/static/default_group_icon.png", profile_name="Cat")
                
            with ui.tab_panel('About'):
                ui.label('This is the second tab')

        # with ui.page_sticky(position='bottom-right', x_offset=20, y_offset=20):
        #     ui.button(on_click=footer.toggle).props('fab icon=contact_support')


        # the page content consists of multiple tab panels





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

    ui.run_with(app, title="Fedigroup", favicon="app/static/default_group_icon.png")