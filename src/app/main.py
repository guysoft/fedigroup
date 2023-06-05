import re
from fastapi import FastAPI, Request, Header, Response, Form, Depends, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from typing import Optional, List
# from sqlalchemy.orm import Session
from sqlmodel import Session
from app.make_ssh_key import generate_keys

from app.crud import get_group_by_name, create_group, add_member_to_group, remove_member_grom_group, \
get_members_list, get_note, get_groups, create_federated_note, get_boost_by_note_id, \
update_oauth_code, get_settings_secret, get_actor_or_create, get_recipients_from_note

from app.db import Group, Members, SessionLocal, database
from app.common import get_config, DIR, as_form, get_group_path, SERVER_DOMAIN, SERVER_URL, datetime_str, \
is_local_actor, get_handle_name, init_fs, is_valid_group_name

from app.schemas import GroupCreateForm, OauthLogin
from app.send_group import save_message_and_boost
import json
from app.http_sig import send_signed, verify_post_headers
from app.get_federated_data import get_actor_inbox, actor_to_address_format, get_profile, get_actor_url
import time
import os.path
from urllib.parse import urlparse
import starlette
from fastapi_login import LoginManager
from fastapi.responses import JSONResponse
from starlette.responses import RedirectResponse
from app.mastodonapi_login import oauth_login, get_access_token, confirm_actor_valid

from app.auth import Settings, User

from fastapi_another_jwt_auth import AuthJWT
from fastapi_another_jwt_auth.exceptions import AuthJWTException
import app.frontend as frontend

from app.db import get_db

config = get_config()
SERVER_DOMAIN = config["main"]["server_url"]
UPLOAD_FOLDER = config["main"]["upload_folder"]
SERVER_URL = "https://" + SERVER_DOMAIN
DEFAULT_ICON = f"{SERVER_URL}/static/default_group_icon.png"

from app.db import SessionLocal, init_db
init_db(SessionLocal)
init_fs()

app = FastAPI()

templates = Jinja2Templates(directory=os.path.join(DIR, "templates"))
app.mount("/static", StaticFiles(directory=os.path.join(DIR, "static")), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_FOLDER), name="static")

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
    with open(public_default_gpg_path, encoding="utf-8") as f:
        return_value = f.read()
    return return_value

@app.head("/noui")
@app.get("/noui")
async def root(request: Request, db: Session = Depends(get_db), Authorize: AuthJWT = Depends()):
    Authorize.jwt_optional()
    username = Authorize.get_jwt_subject()
    logged_in = username is not None
    page_data = {
        "request": request,
        "data": {
            "logged_in": logged_in,
            "username": username
        }
    }
    return templates.TemplateResponse("index.html", page_data)

@app.post("/create_group_post")
async def create_group_post(request: Request, group_name: str, display_name: str, description: str, creator_handle: str, profile_picture: str= "default", cover_photo: str = "default", db: Session = Depends(get_db)):
    item = {}
    if not is_valid_group_name(group_name):
        return {"message": "Group name is invalid", "success": False}
     
    actor = get_actor_or_create(db, creator_handle)

    item["name"] = group_name
    item["display_name"] = display_name
    item["description"] = description
    item["profile_picture"] = profile_picture
    item["cover_photo"] = cover_photo
    item["creator_id"] = actor.id
    item["discoverable"] = True

    if item["profile_picture"] is None or item["profile_picture"] == "null":
        item["profile_picture"] = "default"
    if item["cover_photo"] is None or item["cover_photo"] == "null":
        item["cover_photo"] = "default"
    
    db_group = get_group_by_name(db, name=group_name)
    if db_group is not None:
        return {"message": f"Error: group {name} already exists", "success": False}
    
    try:
        new_group_db = create_group(db=db, item=item)
        return {"success": True, "id": f"{new_group_db.name}"}
    except Exception as e:
        return {"success": False, "message": f"{e}"}

@app.get("/ostatus_subscribe?acct={id}")
async def subscribe(request: Request, id: str):
    return {"error": "Not implemented"}

# Instances this instance is aware of
@app.get("/api/v1/instance/peers")
async def instance_peers(request: Request):
    return [SERVER_URL]

# Instances this instance is aware of
@app.get("/api/v1/instance")
async def instance(request: Request):
    # TODO implement
    return [SERVER_URL]

def get_context():
    return ["https://www.w3.org/ns/activitystreams",
    SERVER_URL + "/static/schemas/litepub-0.1.jsonld",
    {
        "@language":"und"
    }]

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
    if db_group is None:
        return {"error": "Group not found"}

    context = get_context()
    id_return = SERVER_URL + "/group/" + id
    context_type = "Person" # This is an equivelent of a "Persion"
    following = SERVER_URL + "/group/" + id + "/following"
    followers = SERVER_URL + "/group/" + id + "/followers"
    inbox = SERVER_URL + "/group/" + id + "/inbox"
    outbox = "None"
    featured = SERVER_URL + "/group/" + id + "/featured"
    # Note preferredUsername has to be the same as name
    preferredUsername = db_group.display_name
    manuallyApprovesFollowers = False
    discoverable = db_group.discoverable
    name = db_group.name
    summary = db_group.description
    
    url = SERVER_URL + "/group/" + id
    publicKey = {"id": SERVER_URL + "/group/" + id + "#main-key","owner": SERVER_URL + "/" + id,"publicKeyPem": get_default_gpg()}
    tag = []
    attachment = []
    endpoints = {"oauthAuthorizationEndpoint":SERVER_URL + "/oauth/authorize","oauthRegistrationEndpoint": SERVER_URL + "/api/v1/apps","oauthTokenEndpoint": SERVER_URL + "/oauth/token","sharedInbox": SERVER_URL + "/inbox","uploadMedia": SERVER_URL +"/api/ap/upload_media"}

    icon = {"type": "Image","url": f"{SERVER_URL}{db_group.profile_picture}"}
    if db_group.profile_picture == "default":
        icon = {"type": "Image","url": DEFAULT_ICON}

    image = {"type": "Image","url": f"{SERVER_URL}{db_group.cover_photo}"}
    if db_group.cover_photo == "default":
        image = {"type": "Image","url": DEFAULT_ICON}

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
    # return response
    accept = request.headers["accept"]
    print(accept)
    if "json" in accept:
        return response

    data = f'''
    <html>
        <head>
            <title>Some HTML in here</title>
        </head>
        <body>
            <h1>Group Name: {id}</h1></br>
            <h2>{summary}</h1></br>
            <img src={icon["url"]} /> </h1></br>
            <img src={image["url"]} /> </h1></br>
        </body>
    </html>
    '''
    response = Response(content=str(data), media_type="html")
    return response

# Example response: curl https://hayu.sh/objects/0c4acc5b-5320-470f-8f39-74f52419746d  -H "Accept: application/activity+json"
# Mastodon example response: curl https://tooot.im/@guysoft/104417134724456390  -H "Accept: application/activity+json"
@app.get("/note/{id}")
async def note(request: Request, id: str, db: Session = Depends(get_db)):
    db_note = get_note(db, note_id=id)
    if db_note is None:
        return {"error": "Status not found"}

    to, cc = get_recipients_from_note(db_note)

    context = get_context()
    # summary = db_group.summary
    
    tag = []
    
    attachment = []

    actor = get_actor_url(db_note.attributed.name)
    note_content = db_note.content
    source = db_note.source

    conversation = ""
    created_at = datetime_str(db_note.created_at)
    replies_count = 0
    sensitive = db_note.sensitive

    note_id = SERVER_URL + "/note/" + str(id)
    
    return_value = {
        "@context": context,
        "actor": actor,
        "id": note_id,
        "type": "Note",
        "attachment": attachment,
        "attributedTo": actor,
        "cc": cc,
        "content": note_content,
        "conversation": conversation,
        "published": created_at,
        "repliesCount": replies_count,
        "sensitive": sensitive,
        "source": source,
        "summary":"",
        "tag": tag,
        "to": to,
    }
    
    data = """
    <html>
        <head>
            <title>Some HTML in here</title>
        </head>
        <body>
            <h1>Note: """ + id + """</h1></br>
            <h2>""" + source + """</h1></br>
        </body>
    </html>
    """

    return handle_activity_html_response(request, return_value, data)

def handle_activity_html_response(request: Request, return_value, data: str):
    response = Response(content=json.dumps(return_value), media_type="application/activity+json")
    # Uncomment to debug
    # return response
    accept = request.headers["accept"]
    print(accept)
    if "json" in accept:
        return response
    response = Response(content=str(data), media_type="html")
    return response


# Example response: curl https://kitch.win/users/guysoft/followers  -H "Accept: application/json"
@app.get("/group/{id}/followers")
def group_members(request: Request, id: str, db: Session = Depends(get_db)):
    db_group = get_group_by_name(db, name=id)
    if db_group is None:
        return {"error": "Group not found"}

    members = []
    for member in get_members_list(db, id):
        members.append(member.member.name)

    
    return_value = {
  "@context": get_context(),
  "first": {
    # "id": SERVER_URL + "/group/" + id  +"/followers?page=1",
    "id": SERVER_URL + "/group/" + id  +"/followers",
    # "next": SERVER_URL + "/group/" + id  +"/followers?page=2",
    "next": SERVER_URL + "/group/" + id  +"/followers",

    "orderedItems": members,
    "partOf": SERVER_URL + "/group/" + id  +"/followers",
    "totalItems": len(members),
    "type": "OrderedCollectionPage"
  },
  "id": SERVER_URL + "/group/" + id  +"/followers",
  "totalItems": len(members),
  "type": "OrderedCollection"
}
    
    response = Response(content=json.dumps(return_value), media_type="application/activity+json")
    return response

# Example response: curl https://hayu.sh/users/guysoft/following  -H "Accept: application/json"
@app.get("/group/{id}/following")
async def group_following(request: Request, id: str, db: Session = Depends(get_db)):
    db_group = get_group_by_name(db, name=id)
    if db_group is None:
        return {"error": "Group not found"}

    return_value = {"@context":["https://www.w3.org/ns/activitystreams", SERVER_URL + "/static/schemas/litepub-0.1.jsonld",
    {"@language":"und"}]
    ,"first":{"id": SERVER_URL +  "/group" + id  + "/following",
    # ,"next":"https://hayu.sh/users/guysoft/following?page=2",
    # "orderedItems":["https://mstdn.social/users/tilvids"
    # ,"https://tooot.im/users/admin"
    # ,"https://indieweb.social/users/commonspub"
    # ,"https://tooot.im/users/talash"
    # ,"https://tooot.im/users/LightBlueScreenOfWindowsUpdate"
    # "https://mastodon.gamedev.place/users/godotengine"],
    "orderedItems": [],
    "partOf": SERVER_URL + "/group/" + id + "/following",
    "totalItems":0,"type":"OrderedCollectionPage"},
    "id": SERVER_URL + "/group/" + id + "/following",
    "totalItems":0,
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
async def read_groups(db: Session = Depends(get_db)):
    return get_groups(db)

# Example response: curl https://hayu.sh/.well-known/webfinger?resource=acct:guysoft@hayu.sh
# Doc https://docs.joinmastodon.org/spec/webfinger/
@app.head("/.well-known/webfinger")
@app.get("/.well-known/webfinger")
async def webfinger(resource: str, db: Session = Depends(get_db)):
    acc_data = resource.split(":")
    id = acc_data[1]
    id_data = acc_data[1].split("@")
    username = id_data[0]
    db_group = get_group_by_name(db, name=username)
    if db_group is None:
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

async def send_follow_accept(inbox, accept_activity, preshared_key_id):
    response = send_signed(inbox, accept_activity, get_default_gpg_private_key_path(), preshared_key_id)
    print(f"Got accept follow request: {response}")



# Shared inbox old code
async def shared_inbox(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    body = json.loads(await request.body())
    # print(body)
    actor = body["actor"]

    request_id = body.get("id", None)
    request_type = body.get("type", None)
    requst_to = body.get("to", None)

    requesting_actor = body.get("actor", None)
    object_str = body.get("object", None)

    # object = json.loads(object_str)
    object = object_str

    # Debug data
    print(request.path_params)
    print("headers:")
    print(request.headers)
    
    print("a:")
    print(await request.form())
    data = [i async for i in request.stream()]
    print(data)
    print("object_str:")
    print(object_str)
    print(object)

    if request_type == "Note":
        if requst_to is not None:
            for to_user in requst_to:
                if to_user == "https://fedigroup-dev.gnethomelinux.com/group/aaa":
                    print("AAA was mentioed")
                    
                    
        print("got a status")
        print("Got mentioed by: ")


    return {}


# @app.head("/group/{id}/inbox")
# @app.get("/group/{id}/inbox")
@app.post("/inbox")
@app.post("/group/{group}/inbox")
async def inbox(request: Request, background_tasks: BackgroundTasks, db: Session = Depends(get_db), group: str = None):
    # called_from = request.url.path
    headers = request.headers
    user_agent = headers.get("user-agent")
    algorithm = headers.get("rsa-sha256")
    signature = headers.get("signature")
    date_sig = headers.get("date")
    # user_to_follow = request.path_params["id"]

    body_bytes = None
    try:
        body_bytes = await request.body()
    except starlette.requests.ClientDisconnect:
        message = "Error: client dissconnected before completting request"
        print(message)
        print(headers)
        return message
    
    body = json.loads(body_bytes.decode())
    # print(body)
    actor = body["actor"]    

    request_id = body.get("id", None)
    request_type = body.get("type", None)
    requesting_actor = body.get("actor", None)
    object_str = body.get("object", None)

    # object = json.loads(object_str)
    object = object_str


    debug = False
    # Debug data
    # print(request.path_params)
    # print("headers:")
    # print(headers)
    # print(signature)
    # print("a:")
    # print(await request.form())
    # data = [i async for i in request.stream()]
    # print(data)
    # print("object_str:")
    # print(object_str)
    # print(object)
    # debug = True

    # Follow request from actor
    incoming_actor_profile = get_profile(actor)
    if "publicKey" in incoming_actor_profile.keys():
        pub_key = incoming_actor_profile["publicKey"]["publicKeyPem"]
    else:
        print("No key for actor")
        print(incoming_actor_profile)
        print(body)
        return "No key for actor"
    url = request.url._url
    
    
    parsed = urlparse(url)
    path = parsed.path
    digest = headers["digest"]
    
    verify_result = verify_post_headers("", pub_key,
                                dict(headers),
                                path, False,
                                digest,
                                body_bytes.decode(), debug)

    if verify_result:
        print("Signiture is valid")

        print("got type: " + str(request_type))
            

        if request_type == "Follow":
            print("Got follow request")

            # requesting_actor = object.get("actor", None)
            inbox = get_actor_inbox(requesting_actor)            
            preshared_key_id = get_group_path(group) + "#main-key"

            # Add to follower collection
            member_relation = {
                "group": group,
                "member": actor_to_address_format(requesting_actor)
                }
            result = add_member_to_group(db=db, item=member_relation)

            accept_activity = {
                '@context': 'https://www.w3.org/ns/activitystreams', 
                'id': get_group_path(group) + '#accepts/follows/' + str(time.time()),
                'type': 'Accept',
                'actor': get_group_path(group),
                'object': {
                    'id': request_id,
                    'type': 'Follow',
                    'actor': requesting_actor,
                    'object': get_group_path(group)
                    }
            }

            if result is not None:
                # Send back accept

                # response = await send_signed(inbox, accept_activity, get_default_gpg_private_key_path(), preshared_key_id)
                # print(response)
                background_tasks.add_task(send_follow_accept, inbox, accept_activity, preshared_key_id)
            else:
                print("Error: got none reply for add_member_to_group")

        elif request_type == "Accept":
            print("Got accepted!")
            print(object)
            # send_signed()
            # TODO: Add add following to db
        elif request_type == "Undo":
            print("Got unfollow request")
            # Add to follower collection
            member_relation = {
                "group": group,
                "member": actor_to_address_format(requesting_actor)
                }
            result = remove_member_grom_group(db=db, item=member_relation)
            # background_tasks.add_task(send_follow_accept, inbox, accept_activity, preshared_key_id)
        elif request_type == "Announce":
            note_boosted = body["object"]
            print("Got a boost to status: " + str(note_boosted))
            #TODO handle boost addition to db

            print(json.dumps(body))

        elif request_type == "Create":
            object_created = body.get("object", None)
            object_created_type = object_created.get("type", None)
            if object_created_type == "Note":
                object_tos = object_created["to"]
                object_ccs = object_created["cc"]
                object_id = object_created["id"]

                tags = object_created["tag"]

                mentions = []

                for tag in tags:
                    tag_id = tag["href"]
                    if tag["type"] == "Mention":
                        local_actor = actor_to_address_format(tag_id)
                        if local_actor is not None:
                            if local_actor not in mentions:
                                mentions.append(local_actor)

                for recipient in object_tos + object_ccs:
                    recipient_actor = actor_to_address_format(recipient)
                
                if recipient is not None:
                    if recipient not in mentions:
                        mentions.append(recipient)

                local_mentions = []
                for mention in mentions:
                    if is_local_actor(mention):
                        group = get_handle_name(mention)
                        group_db = get_group_by_name(db, group)
                        if group_db is not None:
                            print("Got mention!")
                            local_mentions.append(group)

                if len(local_mentions) > 0:
                    print("Add boost to db and handle mentions")
                    boost_db = get_boost_by_note_id(db, note_id=object_id)
                    if boost_db is None:
                        print(f"processing: {object_id}")
                        background_tasks.add_task(save_message_and_boost, db, object_created, local_mentions)
                    else:
                        print(f"Already got: {object_id}")
                    return "ok"
        elif request_type == "Delete":
            print("Got delete request, unimplemented")


        else:
            print("Got unhandled request type: " + str(body))
            print("request type: " + str(request_type))
    else:
        print("Signature was not valid")
        return "Signature was not valid"

    return

@app.post('/oauth_login_submit')
async def oauth_login_submit(request: Request, form: GroupCreateForm = Depends(OauthLogin.as_form), db: Session = Depends(get_db)):
    scopes = ("read",)
    result = oauth_login(db, form.username, form.login_type,  scopes)

    if result["success"]:
        redirect_url = result["redirect_url"]        
        return RedirectResponse(url=redirect_url, status_code=303)
    return result


@app.post('/oauth_login_code')
@app.get('/oauth_login_code')
async def oauth_login_code(request: Request, code: str, state: str, db: Session = Depends(get_db), Authorize: AuthJWT = Depends()):
    redirect_url = "/protected"
    params = request.path_params

    oauth_code = update_oauth_code(db, state, None)
    if oauth_code is None:
        return {"error": "Code did not match existing expected state"}

    oauth_app = oauth_code.oauth_app
    domain = oauth_app.domain
    client_id = oauth_app.client_id
    client_secret = oauth_app.client_secret
    # code = oauth_code.code
    actor_handle = oauth_code.actor.name
    scopes = oauth_app.scopes

    access_token = get_access_token(db, domain, client_id, client_secret, scopes, code, state, actor_handle)

    if confirm_actor_valid(access_token, domain):
        # Create the tokens and passing to set_access_cookies or set_refresh_cookies
        access_token = Authorize.create_access_token(subject=actor_handle)
        refresh_token = Authorize.create_refresh_token(subject=actor_handle)

        # Set the JWT and CSRF double submit cookies in the response
        Authorize.set_access_cookies(access_token)
        Authorize.set_refresh_cookies(refresh_token)
        
        return {"login": "success"}
    else:
        return {"error": "Code not valid and did not work on instance"}

@app.post('/debug_request')
@app.get('/debug_request')
async def debug_request(request: Request, background_tasks: BackgroundTasks):

    # called_from = request.url.path
    headers = request.headers
    user_agent = headers.get("user-agent")
    algorithm = headers.get("rsa-sha256")
    signature = headers.get("signature")
    date_sig = headers.get("date")

    body_bytes = None
    try:
        body_bytes = await request.body()
    except starlette.requests.ClientDisconnect:
        message = "Error: client dissconnected before completting request"
        print(message)
        print(headers)
        print(request.path_params)
        return message
    
    body = body_bytes.decode()# json.loads(body_bytes.decode())
    print(body)
    print(headers)
    print(request.path_params)


    # Debug data
    # print(request.path_params)
    # print("headers:")
    # print(headers)
    # print(signature)
    # print("a:")
    # print(await request.form())
    # data = [i async for i in request.stream()]
    # print(data)
    # print("object_str:")
    # print(object_str)
    # print(object)
    return {'debug': "request"}


@AuthJWT.load_config
def get_config():
    secret = get_settings_secret(next(get_db()))
    return Settings(authjwt_secret_key=secret)

@app.exception_handler(AuthJWTException)
def authjwt_exception_handler(request: Request, exc: AuthJWTException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message}
    )

@app.post('/login')
def login(user: User, Authorize: AuthJWT = Depends()):
    """
    With authjwt_cookie_csrf_protect set to True, set_access_cookies() and
    set_refresh_cookies() will now also set the non-httponly CSRF cookies
    """
    if user.username != "test" or user.password != "test":
        raise HTTPException(status_code=401,detail="Bad username or password")

    # Create the tokens and passing to set_access_cookies or set_refresh_cookies
    access_token = Authorize.create_access_token(subject=user.username)
    refresh_token = Authorize.create_refresh_token(subject=user.username)

    # Set the JWT and CSRF double submit cookies in the response
    Authorize.set_access_cookies(access_token)
    Authorize.set_refresh_cookies(refresh_token)
    return {"msg":"Successfully login"}

@app.get('/refresh')
@app.post('/refresh')
def refresh(Authorize: AuthJWT = Depends()):
    Authorize.jwt_refresh_token_required()

    current_user = Authorize.get_jwt_subject()
    new_access_token = Authorize.create_access_token(subject=current_user)
    # Set the JWT and CSRF double submit cookies in the response
    Authorize.set_access_cookies(new_access_token)
    return {"msg":"The token has been refresh"}

@app.get('/get_username')
def get_username(Authorize: AuthJWT = Depends()):
    Authorize.jwt_refresh_token_required()
    current_user = Authorize.get_jwt_subject()
    return {"username": current_user}

@app.delete('/logout')
@app.get('/logout')
def logout(request: Request,Authorize: AuthJWT = Depends()):
    """
    Because the JWT are stored in an httponly cookie now, we cannot
    log the user out by simply deleting the cookie in the frontend.
    We need the backend to send us a response to delete the cookies.
    """
    Authorize.jwt_optional()

    Authorize.unset_jwt_cookies()

    return {"msg":"Successfully logout"}


@app.get('/protected')
def protected(Authorize: AuthJWT = Depends()):
    Authorize.jwt_required()

    current_user = Authorize.get_jwt_subject()
    return {"user": current_user}

frontend.init(app)
