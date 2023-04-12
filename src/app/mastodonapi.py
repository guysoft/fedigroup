from mastodon import Mastodon
from app.common import get_config
import secrets

config = get_config()
SERVER_DOMAIN = config["main"]["server_url"]

REDIERCT_URI = f"https://{SERVER_DOMAIN}/oauth_login_code"

def generate_oauth_state():
    return secrets.token_hex(16)

def get_app_id():
    return f"fedigroup@{SERVER_DOMAIN}"

def register_oauth_application(domain, scopes=("read",)):
    url = "https://" + domain
    app_id = get_app_id()
    client_id, client_secret = Mastodon.create_app(app_id,
        api_base_url=url,
        scopes=scopes,
        redirect_uris=[REDIERCT_URI]
    )
    return client_id, client_secret

def get_oauth_url(client_id, client_secret, domain, state, scopes):
    url = "https://" + domain
    mastodon = Mastodon(client_id=client_secret, client_secret=client_secret, api_base_url=url)
    url = mastodon.auth_request_url(client_id=client_id, state=state, scopes=scopes, force_login=True, redirect_uris=REDIERCT_URI)
    return url

def get_mastodon_login(domain, client_id, token):
    url = "https://" + domain
    # To debug add below debug_requests=True
    mastodon = Mastodon(client_id=client_id, api_base_url=url)
    client = mastodon.log_in(code=token, scopes=scopes)
    return client
    