from enum import unique
import sqlalchemy
from pydantic import BaseModel
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
    id: Optional[int] = Field(default=None, primary_key=True)
    preferredUsername: str = Field()
    name: str = Field()
    summary: str = Field()
    icon: str = Field()
    image: str = Field()
    discoverable: bool = Field()


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