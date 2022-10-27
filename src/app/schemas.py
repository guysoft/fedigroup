from typing import List
from pydantic import BaseModel
from sqlmodel import Field, SQLModel, DateTime, Relationship
from .common import as_form
from .db import Actor
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON

class GroupBase(BaseModel):
    pass

class MemberBase(BaseModel):
    pass


class ActorBase(BaseModel):
    pass

class NoteBase(BaseModel):
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

class MemberCreateRemove(MemberBase):
    group: str
    member: str
    
class ActorCreateRemove(ActorBase):
    actor: str

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
    

