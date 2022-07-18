import requests

def get_actor_inbox(actor_url):
    data = get_profile(actor_url)
    inbox = data.get("inbox", None)
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
    except requests.JSONDecodeError:
        print("Error, failed to decode: " + str(actor_url))

    return data