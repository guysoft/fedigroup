from typing import Union
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, DateTime
from .common import as_form
from datetime import datetime

class GroupBase(BaseModel):
    pass

class MemberBase(BaseModel):
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

class MemberCreate(MemberBase):
    group: str
    member: str
    