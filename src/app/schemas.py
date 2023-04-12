from typing import List
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, DateTime, Relationship
from app.common import as_form
from app.db import Actor
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON

class GroupBase(BaseModel):
    pass

class MemberBase(BaseModel):
    pass


class ActorBase(BaseModel):
    pass

class OauthAppBase(BaseModel):
    pass

class OauthCodeBase(BaseModel):
    pass

class NoteBase(BaseModel):
    pass

class BoostBase(BaseModel):
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

@as_form
class OauthLogin(BaseModel):
    username: str

class MemberCreateRemove(MemberBase):
    group: str
    member: str
    
class ActorCreateRemove(ActorBase):
    actor: str

class OauthAppCreateRemove(OauthAppBase):
    domain: str
    client_id: str
    client_secret: str
    scopes: List[str]

class NoteCreate(NoteBase):
    actor: int
    attributed_to: int
    to: List["Actor"] = Relationship(back_populates="name")
    cc: List[int]
    content: str
    source: str
    summary: str
    created_at: datetime
    replies_count: int
    sensitive: bool
    tag: List[int] = []
    attachment: list = []
    # class Config:
    #     arbitrary_types_allowed = True
    
class BoostCreate(BoostBase):
    actor: int
    attributed_to: int
    to: List["Actor"] = Relationship(back_populates="name")
    cc: List[int]
    note_id: str # The boost item id
    source: str
    created_at: datetime
    replies_count: int
    sensitive: bool
    tag: List[int] = []
    attachment: list = []

