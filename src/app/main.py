from fastapi import FastAPI
from fastapi import FastAPI, Request, Header, Response, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional, List
from sqlalchemy.orm import Session
from .make_ssh_key import generate_keys
from .crud import get_group_by_name, create_group
from .db import Group, SessionLocal, database
from .common import get_config, DIR, as_form
from .schemas import GroupCreateForm
import json

import os.path

config = get_config()
SERVER_DOMAIN = config["main"]["server_url"]
SERVER_URL = "https://" + SERVER_DOMAIN


app = FastAPI()

templates = Jinja2Templates(directory=os.path.join(DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(DIR, "static")), name="static")

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
async def startup():
    await database.connect()


@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()


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

@app.head("/")
@app.get("/")
async def root():
    return {"message": "Hello World"}
   
@app.get("/items_j/{id}", response_class=HTMLResponse)
async def read_item(request: Request, id: str):
    return templates.TemplateResponse("item.html", {"request": request, "id": id})

@app.get("/create_group", response_class=HTMLResponse)
async def read_item(request: Request):
    return templates.TemplateResponse("create_group.html", {"request": request, "data": {}})


@app.post("/create_group_submit")
async def read_item(request: Request, form: GroupCreateForm = Depends(GroupCreateForm.as_form), db: Session = Depends(get_db)):
    db_group = get_group_by_name(db, name=form.name)
    if db_group:
        return { "message": "Error: group " + form.name + " already exists", "success": False}
    return create_group(db=db, item=form.dict())

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
async def group_page(request: Request, id: str, db: Session = Depends(get_db)):
    db_group = get_group_by_name(db, name=id)
    if not db_group:
        return {"error": "Group not found"}

    context = get_context()
    id_return = SERVER_URL + "/group/" + id
    context_type = "Forum" # This is an equivelent of a "Persion"
    following = SERVER_URL + "/group/" + id + "/following"
    followers = SERVER_URL + "/group/" + id + "/followers"
    inbox = SERVER_URL + "/group/" + id + "/inbox"
    outbox = "AA"
    featured = SERVER_URL + "/group/" + id + "/featured"
    preferredUsername = db_group.preferredUsername
    manuallyApprovesFollowers = False
    # discoverable = db_group.discoverable
    discoverable = False
    name = db_group.name
    summary = db_group.summary
    url = SERVER_URL + "/group/" + id
    publicKey = {"id": SERVER_URL + "/group/" + id + "#main-key","owner": SERVER_URL + "/" + id,"publicKeyPem": get_default_gpg()}
    tag = []
    attachment = []
    endpoints = {"oauthAuthorizationEndpoint":SERVER_URL + "/oauth/authorize","oauthRegistrationEndpoint": SERVER_URL + "/api/v1/apps","oauthTokenEndpoint": SERVER_URL + "/oauth/token","sharedInbox": SERVER_URL + "/inbox","uploadMedia": SERVER_URL +"/api/ap/upload_media"}

    icon = {"type":"Image","url": SERVER_URL + "/static/" + db_group.icon}
    if db_group.icon == "default":
        icon = {"type":"Image","url": SERVER_URL + "/static/default_group_icon.png"}

    image = {"type":"Image","url": SERVER_URL + "/static/" + db_group.image}
    if db_group.image == "default":
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
    
    response = Response(content=json.dumps(return_value), media_type="application/activity+json")
    # Uncomment to debug
    # return response
    accept = request.headers["accept"]

    if "json" in accept:
        return return_value

    data = """
    <html>
        <head>
            <title>Some HTML in here</title>
        </head>
        <body>
            <h1>Group Name: """ + id + """</h1></br>
            <h2>""" + summary + """</h1></br>
            <img src=""" + image["url"] + """ /> </h1></br>
        </body>
    </html>
    """
    response = Response(content=str(data), media_type="html")
    return response


# Pleroma and Mastodon return this and search it, so I copied
@app.get("/.well-known/host-meta")
async def well_known(request: Request):
    data = """<?xml version="1.0" encoding="UTF-8"?>
<XRD xmlns="http://docs.oasis-open.org/ns/xri/xrd-1.0">
  <Link rel="lrdd" template=""" + SERVER_URL + """/.well-known/webfinger?resource={uri}"/>
</XRD>
    """
    response = Response(content=str(data), media_type="application/xrd+xml")
    return response

# Pleroma and Mastodon return this and search it, so I copied
@app.get("/group/{id}/featured")
async def group_featured(request: Request, id: str):
    orderedItems = []
    data = {
        "@context": get_context(),
        "id": SERVER_URL + "/group/" + id,
        "orderedItems": orderedItems,
        "totalItems": len(orderedItems),
        "type": "OrderedCollection"
    }

    response = Response(content=str(data), media_type="application/jrd+json")
    return response


@app.get("/groups/", response_model=List[Group])
async def read_groups():
    query = groups.select()
    return await database.fetch_all(query)

# Example response: curl https://hayu.sh/.well-known/webfinger?resource=acct:guysoft@hayu.sh
# Doc https://docs.joinmastodon.org/spec/webfinger/
@app.head("/.well-known/webfinger")
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
        aliases = [SERVER_URL + "/group/" + username]
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

        links.append(subscribe)

        subject = "acct:" + id
        return_value = {"aliases": aliases, "links": links, "subject": subject}
        response = Response(content=json.dumps(return_value), media_type="application/jrd+json; charset=utf-8")
        return response
    return {"error": "user not found"}

