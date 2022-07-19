from sqlalchemy.orm import Session
from .schemas import GroupCreate, MemberCreate
from .db import Group, Members, database

# CRUD comes from: Create, Read, Update, and Delete.
def get_group_by_name(db: Session, name: str):
    return db.query(Group).filter(Group.name == name).first()


def create_group(db: Session, item: GroupCreate):
    # item["id"] = 7
    item["icon"] = "default"
    item["image"] = "default"
    item["discoverable"] = True
    
    db_item = Group(**item)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def add_member_to_group(db: Session, item: MemberCreate):
    db_item = Members(**item)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item