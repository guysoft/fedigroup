from typing import Union
from pydantic import BaseModel
from sqlmodel import Field, SQLModel
from .common import as_form

class GroupBase(BaseModel):
    pass


class GroupCreate(GroupBase):
    preferredUsername: str
    name: str
    summary: str
    icon: str
    image: str
    discoverable: bool

@as_form
class GroupCreateForm(BaseModel):
    preferredUsername: str
    name: str
    summary: str