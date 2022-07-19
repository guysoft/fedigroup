from fastapi import FastAPI
from fastapi import FastAPI, Request, Header, Response, Form, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional, List
from sqlalchemy.orm import Session
from .make_ssh_key import generate_keys
from .crud import get_group_by_name, create_group, add_member_to_group
from .db import Group, Members, SessionLocal, database
from .common import get_config, DIR, as_form
from .schemas import GroupCreateForm, MemberCreate
import json
from .http_sig import send_signed
from .get_federated_data import get_actor_inbox, actor_to_address_format

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


def get_default_gpg_private_key_path():
    default_gpg_path = os.path.join(config["main"]["data_folder"], "default_gpg_key")
    private_default_gpg_path = os.path.join(default_gpg_path, "id_rsa")
    return private_default_gpg_path

def get_default_gpg():
    default_gpg_path = os.path.join(config["main"]["data_folder"], "default_gpg_key")
    private_default_gpg_path = os.path.join(default_gpg_path, "id_rsa")
    public_default_gpg_path = os.path.join(default_gpg_path, "id_rsa.pub")
    if not os.path.isfile(private_default_gpg_path):
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

def get_group_path(group):
    return SERVER_URL + "/group/" + group


# @app.head("/group/{id}/inbox")
# @app.get("/group/{id}/inbox")
# async def inbox(request: Request, id: str, db: Session = Depends(get_db)):
#     db_group = get_group_by_name(db, name=id)
#     if not db_group:
#         return {"error": "Group not found"}
    
#     headers = request.headers
#     print("headers:")
#     print(headers)
#     print("Body:")
#     print(await request.body())



# Example response: curl https://hayu.sh/users/guysoft  -H "Accept: application/json"
@app.get("/group/{id}")
async def group_page(request: Request, id: str, db: Session = Depends(get_db)):
    db_group = get_group_by_name(db, name=id)
    if not db_group:
        return {"error": "Group not found"}

    context = get_context()
    id_return = SERVER_URL + "/group/" + id
    context_type = "Person" # This is an equivelent of a "Persion"
    following = SERVER_URL + "/group/" + id + "/following"
    followers = SERVER_URL + "/group/" + id + "/followers"
    inbox = SERVER_URL + "/group/" + id + "/inbox"
    outbox = "AA"
    featured = SERVER_URL + "/group/" + id + "/featured"
    # Note preferredUsername has to be the same as name
    preferredUsername = id # db_group.preferredUsername
    manuallyApprovesFollowers = False
    discoverable = db_group.discoverable
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
        "preferredUsername": id,
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
    
    # return_value = json.loads("""{"@context": ["https://www.w3.org/ns/activitystreams", "https://w3id.org/security/v1"], "id": "https://pleroma.gnethomelinux.com/group/""" + id + """", "inbox": "https://pleroma.gnethomelinux.com/inbox", "preferredUsername": \"""" + id + """", "publicKey": {"id": "https://pleroma.gnethomelinux.com/group/""" + id + """#main-key", "owner": "https://pleroma.gnethomelinux.com/group/""" + id +"""", "publicKeyPem": "BOOP"}, "type": "Person"}""")

    response = Response(content=json.dumps(return_value), media_type="application/activity+json")
    # Uncomment to debug
    return response
    accept = request.headers["accept"]
    print(accept)
    if "json" in accept:
        return response

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

# Example response: curl https://kitch.win/users/guysoft/followers  -H "Accept: application/json"
@app.get("/group/{id}/followers")
def group_members(request: Request, id: str, db: Session = Depends(get_db)):
    db_group = get_group_by_name(db, name=id)
    if not db_group:
        return {"error": "Group not found"}
    
    return_value = {
  "@context": get_context(),
  "first": {
    "id": SERVER_URL + "/group/" + id  +"/followers?page=1",
    "next": SERVER_URL + "/group/" + id  +"/followers?page=2",
    "orderedItems": [],
    "partOf": SERVER_URL + "/group/" + id  +"/followers",
    "totalItems": 0,
    "type": "OrderedCollectionPage"
  },
  "id": SERVER_URL + "/group/" + id  +"/followers",
  "totalItems": 0,
  "type": "OrderedCollection"
}
    
    response = Response(content=json.dumps(return_value), media_type="application/activity+json")
    return response

# Example response: curl https://hayu.sh/users/guysoft/following  -H "Accept: application/json"
@app.get("/group/{id}/following")
async def group_following(request: Request, id: str, db: Session = Depends(get_db)):
    db_group = get_group_by_name(db, name=id)
    if not db_group:
        return {"error": "Group not found"}

    return_value = {"@context":["https://www.w3.org/ns/activitystreams", SERVER_URL + "/schemas/litepub-0.1.jsonld",
    {"@language":"und"}]
    ,"first":{"id": SERVER_URL +  "/group" + id  + "/following",
    # ,"next":"https://hayu.sh/users/guysoft/following?page=2",
    # "orderedItems":["https://mstdn.social/users/tilvids"
    # ,"https://tooot.im/users/admin"
    # ,"https://indieweb.social/users/commonspub"
    # ,"https://tooot.im/users/talash"
    # ,"https://tooot.im/users/LightBlueScreenOfWindowsUpdate"
    # "https://mastodon.gamedev.place/users/godotengine"],
    "orderedItems": ["https://hayu.sh/users/guysoft"],
    "partOf": SERVER_URL + "/group/" + id + "/following",
    "totalItems":4,"type":"OrderedCollectionPage"},
    "id": SERVER_URL + "/group/" + id + "/following",
    "totalItems":4,
    "type":"OrderedCollection"}

    response = Response(content=json.dumps(return_value), media_type="application/activity+json")
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

    response = Response(content=str(data), media_type="application/activity+json")
    return response


@app.get("/groups/", response_model=List[Group])
async def read_groups():
    query = groups.select()
    return await database.fetch_all(query)

# Example response: curl https://hayu.sh/.well-known/webfinger?resource=acct:guysoft@hayu.sh
# Doc https://docs.joinmastodon.org/spec/webfinger/
@app.head("/.well-known/webfinger")
@app.get("/.well-known/webfinger")
async def webfinger(request: Request, resource: str, db: Session = Depends(get_db)):
    acc_data = resource.split(":")
    id = acc_data[1]
    id_data = acc_data[1].split("@")
    username = id_data[0]
    db_group = get_group_by_name(db, name=username)
    if not db_group:
        return {"error": "Group not found"}

    # id_data = id.split("@")
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
            "rel": "http://webfinger.net/rel/profile-page",
            "type":"text/html"
            }
        links.append(rel_self)
        
        subscribe = {
            "rel": "http://ostatus.org/schema/1.0/subscribe",
            "template": SERVER_URL + "/ostatus_subscribe?acct={uri}"
        }
        
        # Don't think we need this, PR if you think you do
        # links.append(subscribe)

        subject = "acct:" + id
        return_value = {"aliases": aliases, "links": links, "subject": subject}
        
        # Override for now, this works, the top does not, not sure why
        # return_value = json.loads('{"subject": "acct:' + acc_data[1] + '", "links": [{"href": "https://pleroma.gnethomelinux.com/group/' + username + '", "rel": "self", "type": "application/activity+json"}]}')
        
        response = Response(content=json.dumps(return_value), media_type="application/jrd+json; charset=utf-8")
        return response
    return {"error": "user not found"}


# example call: curl https://mastodon.social/nodeinfo/2.0
@app.get("nodeinfo/2.0")
def mastodon_node_info():
    return_value = {"version":"2.0","software":
    {"name":"fedigroup","version":"1.0.0"}
    ,"protocols":["activitypub"],
    "services":{"outbound":[],"inbound":[]},
    "usage":
    {"users":{"total":1,"activeMonth":1,"activeHalfyear":1},
    "localPosts":1},"openRegistrations":True,"metadata":[]}
    response = Response(content=json.dumps(return_value), media_type="application/json; charset=utf-8")
    return response


# @app.head("/group/{id}/inbox")
# @app.get("/group/{id}/inbox")
@app.post("/group/{group}/inbox")
async def inbox(request: Request, group: str, db: Session = Depends(get_db)):
    body = await request.body()

    headers = request.headers
    user_agent = headers.get("user-agent")
    algorithm = headers.get("rsa-sha256")
    signature = headers.get("signature")
    date_sig = headers.get("date")
    # user_to_follow = request.path_params["id"]
    print(request.path_params)
    print("headers:")
    print(headers)
    print(signature)
    print("Body:")
    body = json.loads(await request.body())
    print(body)

    print("a:")
    print(await request.form())
    print("b:")
    # print(await request.json())
    print("c:")
    # print(await )
    data = [i async for i in request.stream()]
    print(data)

    request_id = body.get("id", None)
    request_type = body.get("type", None)
    requesting_actor = body.get("actor", None)
    object_str = body.get("object", None)
    print("object_str:")
    print(object_str)
    # object = json.loads(object_str)
    object = object_str

    print(object)

    if request_type == "Follow":
        # Follow request from actor

        # TODO VERRIFY REQUST IS LEGIT
        print("Object")
        print(object)
        # requesting_actor = object.get("actor", None)
        inbox = get_actor_inbox(requesting_actor)

        accept_activity = {'@context': 'https://www.w3.org/ns/activitystreams', 
        'id': get_group_path(group) + '#accepts/follows/',
         'type': 'Accept',
          'actor': get_group_path(group),
           'object': {'id': requesting_actor + '#follows/',
            'type': 'Follow',
             'actor': requesting_actor,
              'object': get_group_path(group)}
              }
            
        preshared_key_id = get_group_path(group) + "#main-key"

        # Add to follower collection
        member_relation = {
            "group": group,
            "member": actor_to_address_format(requesting_actor)
            }
        add_member_to_group(db=db, item=member_relation)


        # Send back accept
        response = await send_signed(inbox, accept_activity, get_default_gpg_private_key_path(), preshared_key_id)

        print(response)
        return
    if request_type == "Accept":
        print("Got accepted!")
        print(object)
        # send_signed()
        # TODO: Add add following to db

    return
    