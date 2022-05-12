from fastapi import FastAPI
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
import os.path

DIR = os.path.dirname(__file__)
SERVER_DOMAIN = "localhost:9090"
SERVER_URL = "http://" + SERVER_DOMAIN

# SERVER_DOMAIN = "pleroma.gnethomelinux.com"
# SERVER_URL = "https://" + SERVER_DOMAIN

app = FastAPI()
templates = Jinja2Templates(directory=os.path.join(DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(DIR, "static")), name="static")



@app.get("/")
async def root():
    return {"message": "Hello World"}
   
@app.get("/items_j/{id}", response_class=HTMLResponse)
async def read_item(request: Request, id: str):
    return templates.TemplateResponse("item.html", {"request": request, "id": id})


@app.get("/ostatus_subscribe?acct={id}")
async def subscribe(request: Request, id: str):
    return {"error": "Not implemented"}

@app.get("/group/{id}", response_class=HTMLResponse)
async def goup_page(request: Request, id: str):
    return """
    <html>
        <head>
            <title>Some HTML in here</title>
        </head>
        <body>
            <h1>Not implemented</h1>
        </body>
    </html>
    """

# Example response: curl https://hayu.sh/.well-known/webfinger?resource=acct:guysoft@hayu.sh
# Doc https://docs.joinmastodon.org/spec/webfinger/
@app.get("/.well-known/{id}")
async def webfinger(request: Request, id: str):
    id_data = id.split("@")
    username = id_data[0]
    server = None
    if len(id_data) > 1:
        server = id_data[1]
    if server is not None and server == SERVER_DOMAIN:
        aliases = [SERVER_URL + "/" + id]
        links = []
        rel_self = {"href": SERVER_URL + "/group/" + username,
                    "rel":"self",
                    "type":"application/activity+json"}
        links.append(rel_self)

        rel_self = {
            "href": SERVER_URL + "/group/" + username,
            "rel":"self",
            "type":"text/html"
            }
        links.append(rel_self)
        
        subscribe = {
            "rel": "http://ostatus.org/schema/1.0/subscribe",
            "template": SERVER_URL + "/ostatus_subscribe?acct={uri}"
        }

        subject = "acct:" + id
        return {"aliases": aliases, "links": links, "subject": subject}
    return {"error": "user not found"}

