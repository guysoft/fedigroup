from mastodon import Mastodon
from app.common import get_config
import secrets

config = get_config()
SERVER_DOMAIN = config["main"]["server_url"]

REDIERCT_URI_BACKEND = f"https://{SERVER_DOMAIN}/oauth_login_code"
REDIERCT_URI_FRONTEND = f"https://{SERVER_DOMAIN}/oauth_login_code_frontend"

def generate_oauth_state():
    return secrets.token_hex(16)

def get_app_id():
    return f"fedigroup@{SERVER_DOMAIN}"

def d2url(domain):
    return "https://" + domain

def register_oauth_application(domain, scopes=("read",)):
    url = d2url(domain)
    app_id = get_app_id()
    client_id, client_secret = Mastodon.create_app(app_id,
        api_base_url=url,
        scopes=scopes,
        redirect_uris=["urn:ietf:wg:oauth:2.0:oob", REDIERCT_URI_BACKEND, REDIERCT_URI_FRONTEND]
    )
    return client_id, client_secret

def get_oauth_url(client_id, client_secret, domain, state, scopes, redirect_url):
    url = d2url(domain)
    mastodon = Mastodon(client_id=client_id, client_secret=client_secret, api_base_url=url)
    url = mastodon.auth_request_url(client_id=client_id, state=state, scopes=scopes, force_login=True, redirect_uris=redirect_url)
    return url

def get_mastodon_login(domain, client_id, token):
    url = d2url(domain)
    # To debug add below debug_requests=True
    mastodon = Mastodon(client_id=client_secret, api_base_url=url)
    client = mastodon.log_in(code=token, scopes=scopes)
    return client
