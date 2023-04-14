from fastapi import FastAPI, Request, Header, Response, Form, Depends, BackgroundTasks, HTTPException
from app.db import get_db
from sqlmodel import Session
from app.crud import update_oauth_code
from app.mastodonapi import confirm_actor_valid
import asyncio
from nicegui import Client, ui

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
        await client.connected()
        await asyncio.sleep(2)

        # username = await ui.run_javascript('Date()')
        ui.label(f'Welcome user: {await get_username(ui)}')


    @ui.page('/oauth_login_code_frontend')
    async def oauth_login_code_frontend(request: Request, client: Client, code: str, state: str, db: Session = Depends(get_db)) -> None:

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

    ui.run_with(app, title="Fedigroup")