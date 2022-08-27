from enum import unique
import sqlalchemy
from pydantic import BaseModel
from datetime import datetime

from sqlmodel import Field, SQLModel
from sqlalchemy import UniqueConstraint
from .common import get_config
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer
from typing import Optional
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


class Actor(SQLModel, table=True):
    __tablename__ = "actors"
    __table_args__ = (UniqueConstraint("name"),)
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field()


# https://www.w3.org/TR/activitypub/#followers
class Members(SQLModel, table=True):
    __tablename__ = "groups_members"
    id: Optional[int] = Field(default=None, primary_key=True)
    group: int = Field(default=None, foreign_key="groups.id")
    member: int = Field(default=None, foreign_key="actors.id")
    created_at: datetime = Field(default_factory=datetime.utcnow, nullable=False)

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
)
SQLModel.metadata.create_all(engine)


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)