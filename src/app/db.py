import enum
import sqlalchemy
from pydantic import BaseModel
from datetime import datetime

from sqlmodel import Field, ARRAY, Relationship, SQLModel, select, String
from sqlalchemy import UniqueConstraint
from app.common import get_config
from sqlalchemy.orm import sessionmaker, backref
from sqlmodel import Session
from sqlalchemy import Column, Integer, Enum
from typing import Dict, List, Optional
from sqlalchemy.dialects.postgresql import JSON
import databases
import secrets
import string
SECRET_SIZE = 10

config = get_config()
DATABASE_URL = config["main"]["database_url"]

DATABASE_URL = config["main"]["database_url"]
database = databases.Database(DATABASE_URL)

class Setting(SQLModel, table=True):
    __tablename__ = "settings"
    __table_args__ = (UniqueConstraint("name"),)
    name: str = Field(primary_key=True)
    text_setting: str = Field(nullable=True)
    boolean_setting: bool = Field(nullable=True)
    integer_setting: int = Field(nullable=True)
    float_setting: float = Field(nullable=True)

class RecipientType(str, enum.Enum):
    to = "to"
    cc = "cc"

class Group(SQLModel, table=True):
    __tablename__ = "groups"
    __table_args__ = (UniqueConstraint("name"),)
    id: int = Field(default=None, primary_key=True)
    display_name: str = Field()
    name: str = Field()
    description: str = Field()
    profile_picture: str = Field()
    cover_photo: str = Field()
    discoverable: bool = Field()

    creator_id: int = Field(default=None, foreign_key="actors.id")
    creator: Optional["Actor"] = Relationship(back_populates="created_groups")

    members: List["Members"] = Relationship(back_populates="group")

# https://www.w3.org/TR/activitypub/#followers
class Members(SQLModel, table=True):
    __tablename__ = "groups_members"
    __table_args__ = {'extend_existing': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    group_id: int = Field(default=None, foreign_key="groups.id")
    group: Optional[Group] = Relationship(back_populates="members")
    
    member_id: int = Field(default=None, foreign_key="actors.id")
    member: Optional["Actor"] = Relationship(back_populates="groups_in")

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

class NoteRecipients(SQLModel, table=True):
    __tablename__ = "notes_recipients"
    __table_args__ = {'extend_existing': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    note_id: int = Field(default=None, foreign_key="notes.id")
    url: str = Field()
    type: RecipientType = Field(sa_column=Column(Enum(RecipientType)))

    note: "Note" = Relationship(back_populates="recipients")
    
    # If the url is an actor, store it so we can look up mentions
    actor_id: int = Field(default=None, foreign_key="actors.id", nullable=True)
    actor: Optional["Actor"] = Relationship(back_populates="mentions")


class BoostRecipients(SQLModel, table=True):
    __tablename__ = "boosts_recipients"
    __table_args__ = {'extend_existing': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    boost_id: int = Field(default=None, foreign_key="boosts.id")
    url: str = Field()
    type: RecipientType = Field(sa_column=Column(Enum(RecipientType)))

    boost_relation: "Boost" = Relationship(back_populates="recipients")
    
    # If the url is an actor, store it so we can look up mentions
    actor_id: int = Field(default=None, foreign_key="actors.id", nullable=True)
    actor: Optional["Actor"] = Relationship(back_populates="boost_mentions")

class Actor(SQLModel, table=True):
    __tablename__ = "actors"
    __table_args__ = (UniqueConstraint("name"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    profile_picture: str = Field()

    # based of this comment: https://github.com/tiangolo/sqlmodel/issues/10#issuecomment-1020647477
    notes: List["Note"] = Relationship(back_populates="actor",
    sa_relationship_kwargs={"primaryjoin": "Note.actor_id==Actor.id"})

    boosts: List["Boost"] = Relationship(back_populates="actor",
    sa_relationship_kwargs={"primaryjoin": "Boost.actor_id==Actor.id"})
    
    mentions: List[NoteRecipients] = Relationship(back_populates="actor")
    boost_mentions: List[BoostRecipients] = Relationship(back_populates="actor")

    groups_in: List[Members] = Relationship(back_populates="member")
    
    created_groups: List[Group] = Relationship(back_populates="creator")

    codes: List["OauthCode"] = Relationship(back_populates="actor")



# Notes are in-server status messages
class Note(SQLModel, table=True):
    __tablename__ = "notes"
    __table_args__ = {'extend_existing': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    attachment: list = Field(default=[], sa_column=Column(JSON))

    actor_id: Optional[int] = Field(default=None, foreign_key="actors.id")
    actor: Optional[Actor] = Relationship(sa_relationship_kwargs={"primaryjoin": "Note.actor_id==Actor.id"})
    
    attributed_id: int = Field(default=None, foreign_key="actors.id")
    attributed: Optional[Actor] = Relationship(sa_relationship_kwargs={"primaryjoin": "Note.attributed_id==Actor.id"})
    
    # to: List["Actor"] = Relationship(back_populates="note_to")
    # cc: List["Actor"] = Relationship(back_populates="note_cc")

    content: str = Field()
    source: str = Field()
    summary: Optional[str] = None
    # # I think this is used in OStatus stuff: https://socialhub.activitypub.rocks/t/context-vs-conversation/578/7
    # # conversation: str = Field()
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    replies_count: int = Field(default=0)
    sensitive: bool = Field(default=True, nullable=False)
    # # class Config:
    # #     arbitrary_types_allowed = True

    recipients: List[NoteRecipients] = Relationship(back_populates="note")


# Boosts are announce status messages from other server, we also save the content so we can search for it
class Boost(SQLModel, table=True):
    __tablename__ = "boosts"
    __table_args__ = {'extend_existing': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    attachment: list = Field(default=[], sa_column=Column(JSON))

    actor_id: Optional[int] = Field(default=None, foreign_key="actors.id")
    actor: Optional[Actor] = Relationship(sa_relationship_kwargs={"primaryjoin": "Boost.actor_id==Actor.id"})
    
    attributed_id: int = Field(default=None, foreign_key="actors.id")
    attributed: Optional[Actor] = Relationship(sa_relationship_kwargs={"primaryjoin": "Boost.attributed_id==Actor.id"})

    original_poster_id: Optional[int] = Field(default=None, foreign_key="actors.id")
    original_poster: Optional[Actor] = Relationship(sa_relationship_kwargs={"primaryjoin": "Boost.original_poster_id==Actor.id"})
    
    # to: List["Actor"] = Relationship(back_populates="note_to")
    # cc: List["Actor"] = Relationship(back_populates="note_cc")

    content: str = Field()
    note_id: str = Field() # What we are boosting
    
    in_reply_to_id: Optional[int] = Field(default=None, foreign_key="boosts.id")
    comments: List["Boost"] = Relationship(
        sa_relationship_kwargs=dict(
            cascade="all",
            backref=backref("in_reply_to", remote_side="Boost.id"),
        )
    )
    
    source: Dict = Field(default=[], sa_column=Column(JSON))
    original_time: datetime = Field(nullable=False)
    summary: Optional[str] = None
    # # I think this is used in OStatus stuff: https://socialhub.activitypub.rocks/t/context-vs-conversation/578/7
    # # conversation: str = Field()
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)
    sensitive: bool = Field(default=True, nullable=False)
    # # class Config:
    # #     arbitrary_types_allowed = True

    recipients: List[BoostRecipients] = Relationship(back_populates="boost_relation")


class Tag(SQLModel, table=True):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("name"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field()


class NoteTags(SQLModel, table=True):
    __tablename__ = "notes_tags"
    __table_args__ = {'extend_existing': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    note: int = Field(default=None, foreign_key="notes.id")
    tag: int = Field(default=None, foreign_key="tags.id")


class OauthApp(SQLModel, table=True):
    __tablename__ = "oauth_app"
    __table_args__ = {'extend_existing': True}
    id: Optional[int] = Field(default=None, primary_key=True)
    domain: str = Field()
    client_id: str = Field()
    client_secret: str = Field()
    scopes: List[str] = Field(sa_column=Column(ARRAY(String)))

    codes: List["OauthCode"] = Relationship(back_populates="oauth_app")


class OauthCode(SQLModel, table=True):
    __tablename__ = "oauth_codes"
    __table_args__ = {'extend_existing': True}
    id: Optional[int] = Field(default=None, primary_key=True)

    oauth_app_id: int = Field(foreign_key="oauth_app.id")
    oauth_app: OauthApp = Relationship(back_populates="codes",
    sa_relationship_kwargs={"primaryjoin": "OauthCode.oauth_app_id==OauthApp.id",
    "viewonly": True})
    
    actor_id: int = Field(foreign_key="actors.id")
    actor: Actor = Relationship(back_populates="codes")

    state: str = Field()
    code: Optional[str] = Field(default=None)
    
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

# Init
engine = sqlalchemy.create_engine(
    DATABASE_URL, 
    # echo=True
)
# SQLModel.metadata.create_all(engine)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, class_=Session)

# init config values
def init_db(SessionLocal):
    db = SessionLocal()
    login_secret = "login_secret"
    secret = db.exec(select(Setting).where(Setting.name == login_secret)).first()

    if secret is None:
        item = {
            "name": login_secret,
            "text_setting": ''.join(secrets.choice(string.ascii_uppercase + string.ascii_lowercase) for i in range(SECRET_SIZE))
        }

        db_item = Setting(**item)
        db.add(db_item)
        db.commit()
        db.refresh(db_item)

# Dependency
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()