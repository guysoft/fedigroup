from sqlalchemy.orm import Session
from .schemas import GroupCreate, MemberCreateRemove
from .db import Group, Members, database
from sqlmodel import select

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


def add_member_to_group(db: Session, item: MemberCreateRemove):
    # Check if exists:
    member_in_group = db.query(Members).filter((Members.group == item["group"]) & (Members.member == item["member"])).first()
    if not member_in_group:
        db_item = Members(**item)
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item
    return

def remove_member_grom_group (db: Session, item: MemberCreateRemove):
    # Check if exists:
    member_in_group = db.query(Members).filter((Members.group == item["group"]) & (Members.member == item["member"])).delete()
    # db_item = Members(**item)
    db.commit()
    return member_in_group


def get_members_list(db: Session, group: str):
    return db.query(Members).filter(Group.name == group)