import os
import yaml
import inspect
from typing import Type, Tuple
from urllib.parse import urljoin, quote_plus, urlparse

from fastapi import Form
from pydantic import BaseModel
from pydantic.fields import ModelField

DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(DIR, "config.yml")

def ensure_dir(d, chmod=0o777):
    """
    Ensures a folder exists.
    Returns True if the folder already exists
    """
    if not os.path.exists(d):
        os.makedirs(d, chmod)
        os.chmod(d, chmod)
        return False
    return True

def get_config():
    with open(CONFIG_PATH) as f:
        return yaml.load(f, Loader=yaml.FullLoader)
    return

config = get_config()
SERVER_DOMAIN = config["main"]["server_url"]
SERVER_URL = "https://" + SERVER_DOMAIN

def as_form(cls: Type[BaseModel]):
    new_parameters = []

    for field_name, model_field in cls.__fields__.items():
        model_field: ModelField  # type: ignore

        new_parameters.append(
             inspect.Parameter(
                 model_field.alias,
                 inspect.Parameter.POSITIONAL_ONLY,
                 default=Form(...) if not model_field.required else Form(model_field.default),
                 annotation=model_field.outer_type_,
             )
         )

    async def as_form_func(**data):
        return cls(**data)

    sig = inspect.signature(as_form_func)
    sig = sig.replace(parameters=new_parameters)
    as_form_func.__signature__ = sig  # type: ignore
    setattr(cls, 'as_form', as_form_func)
    return cls

def get_group_path(group) -> str:
    return SERVER_URL + "/group/" + group

def datetime_str(date_time) -> str:
    return_value = date_time.isoformat().replace("+00:00", "Z")
    if not return_value.endswith("Z"):
        return_value += "Z"
    return return_value


def multi_urljoin(*parts) -> str:
    """Joins url strings together with escapes for arguments

    Returns:
        str: Joined string with strings escaped
    """
    return urljoin(parts[0], "/".join(quote_plus(part.strip("/"), safe="/") for part in parts[1:]))

def get_handle_name(actor_handle):
    # Remove proceeding @ if needed
    if actor_handle.startswith("@"):
        actor_handle = actor_handle[1:]

    if "@" not in actor_handle:
        return None

    user = actor_handle.split("@")[0]
    return user

def is_local_actor(actor_handle):
    # Remove proceeding @ if needed
    if actor_handle.startswith("@"):
        actor_handle = actor_handle[1:]

    if "@" not in actor_handle:
        return False
    
    host = actor_handle.split("@")[1]

    if host == SERVER_DOMAIN:
        user = actor_handle.split("@")[0]
        return True
    return False

def get_server_keys(group: str) -> Tuple[str, str]:
    """
    Return the server keys to share posts
    """
    preshared_key_id = multi_urljoin(SERVER_URL, "group", group) + "#main-key"
    key_path = "/data/default_gpg_key/id_rsa"
    return preshared_key_id, key_path
