from sqlalchemy.orm import Session
from .schemas import GroupCreate, MemberCreateRemove, ActorCreateRemove
from .db import Group, Members, Actor, database
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

def add_actor(db: Session, item: ActorCreateRemove):
    db_item = Actor(**item)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def add_member_to_group(db: Session, item: MemberCreateRemove):
    # Get actor if exists
    actor = db.query(Actor).filter(Actor.name == item["member"]).first()

    if not actor:
        actor_entry = {
            "name": item["member"],
            }
        actor = add_actor(db=db, item=actor_entry)

    # Get group if exists
    group = get_group_by_name(db=db, name=item["group"])

    if group is None:
        print("Error, group does not exist: " + item["group"])
        return

    # Check if exists:
    member_in_group = db.query(Members).filter((Members.group == group.id) & (Members.member == actor.id)).first()
    if not member_in_group:
        # Use id for actor and not the name
        item["member"] = actor.id
        item["group"] = group.id
        db_item = Members(**item)
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item
    return

def remove_member_grom_group (db: Session, item: MemberCreateRemove):
    # Get actor if exists
    actor = db.query(Actor).filter(Actor.name == item["member"]).first()

    if not actor:
        print("Error: actor does not exist in database: " + str(item["member"]))
        return

    # Get group if exists
    group = get_group_by_name(db=db, name=item["group"])

    if group.id is None:
        print("Error, group does not exist: " + item["group"])
        return

    # Check if exists:
    member_in_group = db.query(Members).filter((Members.group == group.id) & (Members.member == actor.id)).delete()
    # db_item = Members(**item)
    db.commit()
    return member_in_group


def get_members_list(db: Session, group: str):
    return db.query(Group, Members, Actor).filter((Group.name == group) & (Actor.id == Members.member))