import enum
import sqlalchemy
from pydantic import BaseModel
from datetime import datetime

from sqlmodel import Field, Relationship, SQLModel
from sqlalchemy import UniqueConstraint
from .common import get_config
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, Enum
from typing import List, Optional
from sqlalchemy.dialects.postgresql import JSON
import databases


config = get_config()
DATABASE_URL = config["main"]["database_url"]

DATABASE_URL = config["main"]["database_url"]
database = databases.Database(DATABASE_URL)

class Group(SQLModel, table=True):
    __tablename__ = "groups"
    __table_args__ = (UniqueConstraint("name"),)
    id: int = Field(default=None, primary_key=True)
    # TODO: Remove preferredUsername
    preferredUsername: str = Field()
    name: str = Field()
    summary: str = Field()
    icon: str = Field()
    image: str = Field()
    discoverable: bool = Field()

# https://www.w3.org/TR/activitypub/#followers
class Members(SQLModel, table=True):
    __tablename__ = "groups_members"
    __table_args__ = {'extend_existing': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    group: int = Field(default=None, foreign_key="groups.id")
    member: int = Field(default=None, foreign_key="actors.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

# These are the notes status, each status is like a thread topic
class Announces(SQLModel, table=True):
    __tablename__ = "groups_topics"
    __table_args__ = {'extend_existing': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    group: int = Field(default=None, foreign_key="groups.id")
    member: int = Field(default=None, foreign_key="actors.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    
    subject: str = Field()
    # note: str = Field()

class Actor(SQLModel, table=True):
    __tablename__ = "actors"
    __table_args__ = (UniqueConstraint("name"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)

    # based of this comment: https://github.com/tiangolo/sqlmodel/issues/10#issuecomment-1020647477
    notes: List["Note"] = Relationship(back_populates="actor",
    sa_relationship_kwargs={"primaryjoin": "Note.actor_id==Actor.id"})

# Notes are in-server status messages
class Note(SQLModel, table=True):
    __tablename__ = "notes"
    __table_args__ = {'extend_existing': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    attachment: list = Field(default=[], sa_column=Column(JSON))

    actor_id: Optional[int] = Field(default=None, foreign_key="actors.id")
    actor: Optional[Actor] = Relationship(sa_relationship_kwargs={"primaryjoin": "Note.actor_id==Actor.id"})
    

    attributed: int = Field(default=None, foreign_key="actors.id")
    
    # to: List["Actor"] = Relationship(back_populates="note_to")
    # cc: List["Actor"] = Relationship(back_populates="note_cc")

    content: str = Field()
    source: str = Field()
    summary: str = Field()
    # # I think this is used in OStatus stuff: https://socialhub.activitypub.rocks/t/context-vs-conversation/578/7
    # # conversation: str = Field()
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    replies_count: int = Field(default=0)
    sensitive: bool = Field(default=False)
    # # class Config:
    # #     arbitrary_types_allowed = True


class Tag(SQLModel, table=True):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("name"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field()


class NoteTags(SQLModel, table=True):
    __tablename__ = "notes_tags"
    __table_args__ = {'extend_existing': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    actor: int = Field(default=None, foreign_key="notes.id")
    actor: int = Field(default=None, foreign_key="tags.id")

class RecipientType(str, enum.Enum):
    to = "to"
    cc = "cc"

class NoteRecipients(SQLModel, table=True):
    __tablename__ = "notes_recipients"
    __table_args__ = {'extend_existing': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    actor: int = Field(default=None, foreign_key="notes.id")
    actor: int = Field(default=None, foreign_key="actors.id")
    type: RecipientType = Field(sa_column=Column(Enum(RecipientType)))


    
# metadata = sqlalchemy.MetaData()

# groups = sqlalchemy.Table(
#     "group",
#     metadata,
#     sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
#     sqlalchemy.Column("preferredUsername", sqlalchemy.String),
#     sqlalchemy.Column("name", sqlalchemy.String, unique=True),
#     sqlalchemy.Column("summary", sqlalchemy.String),
#     sqlalchemy.Column("icon", sqlalchemy.String),
#     sqlalchemy.Column("image", sqlalchemy.String),
#     sqlalchemy.Column("discoverable", sqlalchemy.Boolean),
# )

engine = sqlalchemy.create_engine(
    DATABASE_URL, 
    # echo=True
)
SQLModel.metadata.create_all(engine)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)