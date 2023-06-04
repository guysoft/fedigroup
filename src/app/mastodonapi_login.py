from typing import Tuple, Dict, Any
from app.crud import get_domain_app_id_or_create, add_initial_oauth_code, update_oauth_code
from app.mastodonapi import get_oauth_url, d2url, REDIERCT_URI_BACKEND, REDIERCT_URI_FRONTEND
from mastodon import Mastodon
from mastodon.errors import MastodonUnauthorizedError
from sqlmodel import Session
import requests

debug = False

def oauth_login(db: Session, username_handle: str, login_type: str, scopes: Tuple[str]) -> Dict[str, Any]:
    username_data = username_handle.split("@")
    if len(username_data) != 2:
        return {
            "success": False,
            "error": "username is requried to be in he format user@server.tld, there should be only one at sign"
        }

    redirect_uri = REDIERCT_URI_BACKEND
    if login_type == "frontend":
        redirect_uri = REDIERCT_URI_FRONTEND
    elif login_type == "key":
        redirect_uri = "urn:ietf:wg:oauth:2.0:oob"

    domain = username_data[1]
    user = username_data[0]
    # TODO timeout on fail of server to create token
    oauth_app = get_domain_app_id_or_create(db, domain, scopes)

    client_id = oauth_app.client_id
    client_secret = oauth_app.client_secret

    oauth_code = add_initial_oauth_code(db, scopes, user, oauth_app)

    redirect_url = get_oauth_url(client_id, client_secret, domain, oauth_code.state, scopes, redirect_uri)
    return {
            "success": True,
            "redirect_url": redirect_url,
    }

def get_access_token(db, domain, client_id, client_secret, scopes, code, state, actor_handle) -> Dict[str, Any]:
    url = d2url(domain)
    access_token = None
    try:
        headers  = {
            'User-Agent': 'mastodonpy',
            'Authorization': f'Bearer {code}'
        }

        s = requests.Session()
        s.headers.update(headers)

        data = {'code':  code,
        'redirect_uri': REDIERCT_URI_FRONTEND,
        'grant_type': 'authorization_code',
        'client_id': client_id,
        'client_secret': client_secret,
        'scope': 'read'
        }

        r = s.post(f"{url}/oauth/token", data=data)
        response_data = r.json()

        access_token = response_data["access_token"]


        mastodon = Mastodon(access_token=access_token, api_base_url=url, debug_requests=debug)
        oauth_code = update_oauth_code(db, state, access_token)

        # Test we can see home timeline
        mastodon.timeline_home()
    except MastodonUnauthorizedError:
            return None
    return access_token

def confirm_actor_valid(access_token, domain):
    url = d2url(domain)
    try:
        mastodon = Mastodon(access_token=access_token, api_base_url=url, debug_requests=debug)

        # Test we can see home timeline
        mastodon.timeline_home()

        return True
    except MastodonUnauthorizedError:
        return False

    return False
