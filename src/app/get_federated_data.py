import requests
from urllib.parse import urlparse
from app.common import SERVER_URL, get_group_path, SERVER_DOMAIN

def webfinger(actor_handle):
    # Remove proceeding @ if needed
    if actor_handle.startswith("@"):
        actor_handle = actor_handle[1:]

    if "@" not in actor_handle:
        return
    
    host = actor_handle.split("@")[1]

    if host == SERVER_DOMAIN:
        user = actor_handle.split("@")[0]
        return {"result": "local", "actor_url": get_group_path(user)}

    url = "https://" + host + "/.well-known/webfinger?resource=acct:" + actor_handle

    print("Getting: " + str(url))

    r = requests.get(url)
    data = None
    try:
        data = r.json()
    except requests.JSONDecodeError:
        print("Error, failed to decode webfinger: " + str(url))
    data["result"] = "remote"
    return data

def get_actor_url(actor_handle: str) -> str:
    data = webfinger(actor_handle)
    
    if data["result"] == "local":
        return data["actor_url"]

    links = data["links"]
    for link in links:
        if type(link) == dict and "rel" in link.keys() and "type" in link.keys() and "href" in link.keys():
            if link["rel"] == "self" and link["type"] == "application/activity+json":
                return link["href"]
        
    return

def get_actor_inbox(actor_url, shared=False):
    data = get_profile(actor_url)
    inbox = data.get("inbox", None)
    if shared:
        if "endpoints" in data.keys():
            if "sharedInbox" in data["endpoints"]:
                inbox = data["endpoints"].get("sharedInbox", None)
        
    if inbox is None:
        print("Error: no inbox field in actor url")
    return inbox

def get_profile(actor_url):
    headers = {
        'Accept': 'application/json',
    }
    r = requests.get(actor_url, headers=headers)
    data = None
    try:
        data = r.json()
    except requests.JSONDecodeError as e:
        import traceback
        traceback.format_exc()
        print("Error, failed to decode: " + str(actor_url))

    return data

def actor_to_address_format(actor_url):
    if actor_url == "https://www.w3.org/ns/activitystreams#Public":
        return
    
    parsed = urlparse(actor_url)
    host = parsed.netloc

    if host == SERVER_DOMAIN:
        group_url = SERVER_URL + "/group"
        if actor_url.startswith(group_url):
            handle = actor_url.split(group_url + "/")[1]
            return handle + "@" + SERVER_DOMAIN
            

    data = get_profile(actor_url)

    if "name" not in data.keys():
        return
    
    return data["name"] + "@" + host