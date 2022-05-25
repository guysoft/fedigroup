from fastapi import FastAPI
from fastapi import FastAPI, Request, Header, Response
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional
import yaml
from .make_ssh_key import generate_keys

import os.path

DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(DIR, "config.yml")


def get_config():
    with open(CONFIG_PATH) as f:
        return yaml.load(f, Loader=yaml.FullLoader)
    return

config = get_config()
SERVER_DOMAIN = config["main"]["server_url"]
SERVER_URL = "https://" + SERVER_DOMAIN

app = FastAPI()
templates = Jinja2Templates(directory=os.path.join(DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(DIR, "static")), name="static")


def get_default_gpg():
    default_gpg_path = os.path.join(config["main"]["data_folder"], "default_gpg_key")
    public_default_gpg_path = os.path.join(default_gpg_path, "id_rsa.pub")
    if not os.path.isfile(default_gpg_path):
        print("No default gpg key, creating one")
        generate_keys(default_gpg_path)
    return_value = None
    with open(public_default_gpg_path) as f:
        return_value = f.read()
    return return_value

@app.get("/")
async def root():
    return {"message": "Hello World"}
   
@app.get("/items_j/{id}", response_class=HTMLResponse)
async def read_item(request: Request, id: str):
    return templates.TemplateResponse("item.html", {"request": request, "id": id})


@app.get("/ostatus_subscribe?acct={id}")
async def subscribe(request: Request, id: str):
    return {"error": "Not implemented"}

# Instances this instance is aware of
@app.get("//api/v1/instance/peers")
async def subscribe(request: Request):
    return [SERVER_URL]

def get_context():
    return ["https://www.w3.org/ns/activitystreams",
    SERVER_URL + "/schemas/litepub-0.1.jsonld",
    {
        "@language":"und"
    }]

# Example response: curl https://hayu.sh/users/guysoft  -H "Accept: application/json"
@app.get("/group/{id}")
async def goup_page(request: Request, id: str):
    context = get_context();
    id_return = SERVER_URL + "/group/" + id
    context_type = "Forum" # This is an equivelent of a "Persion"
    following = SERVER_URL + "/group/" + id + "/following"
    followers = SERVER_URL + "/group/" + id + "/followers"
    inbox = SERVER_URL + "/group/" + id + "/inbox"
    outbox = "AA"
    featured = SERVER_URL + "/group/" + id + "/featured"
    preferredUsername = id
    manuallyApprovesFollowers = False
    discoverable = False
    name = "Group: " + id
    summary = "AaA"
    url = SERVER_URL + "/group/" + id
    publicKey = {"id": SERVER_URL + "/group/" + id + "#main-key","owner": SERVER_URL + "/" + id,"publicKeyPem": get_default_gpg()}
    tag = []
    attachment = []
    endpoints = {"oauthAuthorizationEndpoint":SERVER_URL + "/oauth/authorize","oauthRegistrationEndpoint": SERVER_URL + "/api/v1/apps","oauthTokenEndpoint": SERVER_URL + "/oauth/token","sharedInbox": SERVER_URL + "/inbox","uploadMedia": SERVER_URL +"/api/ap/upload_media"}
    icon = {"type":"Image","url": SERVER_URL + "/static/default_group_icon.png"}
    image = {"type":"Image","url": SERVER_URL + "/static/default_group_icon.png"}

    return_value = {
        "@context": context,
        "id": id_return,
        "type": context_type,
        "following": following,
        "followers": followers,
        "inbox": inbox,
        "outbox": outbox,
        "featured": featured,
        "preferredUsername": preferredUsername,
        "name": name,
        "summary": summary,
        "url": url,
        "publicKey": publicKey,
        "tag": tag,
        "attachment": attachment,
        "endpoints": endpoints,
        "icon": icon,
        "image": image,
        "manuallyApprovesFollowers": manuallyApprovesFollowers,
        "discoverable": discoverable,
    }
    
    import json
    response = Response(content=json.dumps(return_value), media_type="application/activity+json")
    return response
    accept = request.headers["accept"]
    print(accept)
    if "json" in accept:
        return return_value

    data = """
    <html>
        <head>
            <title>Some HTML in here</title>
        </head>
        <body>
            <h1>Group Name """ + id + """</h1></br>
        </body>
    </html>
    """
    response = Response(content=str(data), media_type="html")
    return response


# Pleroma and Mastodon return this and search it, so I copied
@app.get("/.well-known/host-meta")
async def goup_page(request: Request):
    data = """<?xml version="1.0" encoding="UTF-8"?>
<XRD xmlns="http://docs.oasis-open.org/ns/xri/xrd-1.0">
  <Link rel="lrdd" template=""" + SERVER_URL + """/.well-known/webfinger?resource={uri}"/>
</XRD>
    """
    response = Response(content=str(data), media_type="application/xrd+xml")
    return response

# Pleroma and Mastodon return this and search it, so I copied
@app.get("/group/{id}/featured")
async def goup_page(request: Request, id: str):
    orderedItems = []
    data = {
        "@context": get_context(),
        "id": SERVER_URL + "/group/" + id,
        "orderedItems": orderedItems,
        "totalItems": len(orderedItems),
        "type": "OrderedCollection"
    }

    response = Response(content=str(data), media_type="application/xrd+xml")
    return response


# Example response: curl https://hayu.sh/.well-known/webfinger?resource=acct:guysoft@hayu.sh
# Doc https://docs.joinmastodon.org/spec/webfinger/
@app.get("/.well-known/webfinger")
async def webfinger(request: Request, resource: str):
    acc_data = resource.split(":")
    id = acc_data[1]
    id_data = acc_data[1].split("@")
    # id_data = id.split("@")
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

