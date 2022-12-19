"""CREATE, READ, UPDATE and DELETE int he database

    Returns:
        _type_: _description_
"""
from typing import List, Optional, Dict, Any
from datetime import datetime
import uuid
from sqlmodel import select, Session
from app.schemas import GroupCreate, MemberCreateRemove, ActorCreateRemove, NoteCreate, BoostCreate
from app.db import Group, Members, Actor, Note, Boost, RecipientType, NoteRecipients, BoostRecipients
from app.common import SERVER_URL, datetime_str

from app.get_federated_data import get_profile, actor_to_address_format, get_actor_url

# CRUD comes from: Create, Read, Update, and Delete.


def get_group_by_name(db: Session, name: str) -> Optional[Group]:
    return db.exec(select(Group).where(Group.name == name)).first()

def get_groups(db: Session) -> Optional[Group]:
    return db.exec(select(Group)).all()

def create_group(db: Session, item: GroupCreate) -> Group:
    # item["id"] = 7
    item["icon"] = "default"
    item["image"] = "default"
    item["discoverable"] = True

    db_item = Group(**item)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def create_internal_note(db: Session, item: NoteCreate) -> Note:
    item["created_at"] = datetime.utcnow()

    def create_recipients_list(recipients: List[str], recipients_type: RecipientType) -> List[NoteRecipients]:
        recipients_add = []
        for recipient in recipients:
            recipient_to_add = {
                "type": recipients_type,
                "url": recipient
            }

            if "https://www.w3.org/ns/activitystreams" not in recipient:
                profile = get_profile(recipient)
                if profile is not None and "type" in profile.keys() and not "Collection" in profile["type"]:
                    # This is an actor, lets store this as a mention
                    recipient_to_add["actor"] = get_handle_from_url_or_create(
                        db, recipient)

            recipients_add.append(NoteRecipients(**recipient_to_add))

        return recipients_add

    cc = create_recipients_list(item["cc"], RecipientType.cc)
    to = create_recipients_list(item["to"], RecipientType.to)

    item["recipients"] = cc + to
    db_note_item = Note(**item)

    db.add(db_note_item)
    db.commit()
    db.refresh(db_note_item)
    return db_note_item

def create_boost(db: Session, item: BoostCreate) -> Boost:
    item["created_at"] = datetime.utcnow()

    def create_recipients_list(recipients: List[str], recipients_type: RecipientType) -> List[BoostRecipients]:
        recipients_add = []
        for recipient in recipients:
            recipient_to_add = {
                "type": recipients_type,
                "url": recipient
            }

            if "https://www.w3.org/ns/activitystreams" not in recipient:
                profile = get_profile(recipient)
                if profile is not None and "type" in profile.keys() and not "Collection" in profile["type"]:
                    # This is an actor, lets store this as a mention
                    recipient_to_add["actor"] = get_handle_from_url_or_create(
                        db, recipient)

            recipients_add.append(BoostRecipients(**recipient_to_add))

        return recipients_add

    cc = create_recipients_list(item["cc"], RecipientType.cc)
    to = create_recipients_list(item["to"], RecipientType.to)

    item["recipients"] = cc + to

    # TODO: Load in content of boost
    item["content"] = ""
    item["source"] = ""
    item["summary"] = ""

    db_boost_item = Boost(**item)

    db.add(db_boost_item)
    db.commit()
    db.refresh(db_boost_item)
    return db_boost_item
    


def add_actor(db: Session, item: ActorCreateRemove) -> Actor:
    db_item = Actor(**item)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item


def get_actor_or_create(db: Session, actor_handle: str) -> Actor:
    # Get actor if exists
    actor = db.exec(select(Actor).where(Actor.name == actor_handle)).first()

    if actor is None:
        actor_entry = {
            "name": actor_handle,
        }
        actor = add_actor(db=db, item=actor_entry)
    return actor


def get_handle_from_url_or_create(db: Session, actor_url: str) -> Actor:
    a = get_actor_or_create(db, actor_to_address_format(actor_url))
    return a


def add_member_to_group(db: Session, item: MemberCreateRemove) -> Optional[Members]:
    actor = get_actor_or_create(db, item["member"])

    # Get group if exists
    group = get_group_by_name(db=db, name=item["group"])

    if group is None:
        print("Error, group does not exist: " + item["group"])
        return None

    # Check if exists:
    member_in_group = db.exec(select(Members, Group).where(
        Group.name == group.name).where(Members.member_id == actor.id)).first()

    if member_in_group is None:
        # Use id for actor and not the name
        item["member"] = actor
        item["group"] = group
        db_item = Members(**item)
        db.add(db_item)
        db.commit()
        db.refresh(db_item)
        return db_item
    return None


def remove_member_grom_group(db: Session, item: MemberCreateRemove) -> Optional[Members]:
    # Get actor if exists
    actor = db.exec(select(Actor).where(Actor.name == item["member"])).first()

    if actor is None:
        print("Error: actor does not exist in database: " +
              str(item["member"]))
        return None

    # Get group if exists
    group = get_group_by_name(db=db, name=item["group"])

    if group is None:
        print("Error, group does not exist: " + item["group"])
        return None

    # Check if exists:
    # TODO: There seems to be a warning here SAWarning: SELECT statement has a cartesian product between FROM element(s) "groups" and FROM element "groups_members".  Apply join condition(s) between each element to resolve.
    member_in_group = db.exec(select(Members).where(
        Members.group_id == group.id).where(Members.member_id == actor.id)).first()
    # db_item = Members(**item)
    if member_in_group is not None:
        db.delete(member_in_group)
        db.commit()
    return member_in_group


def get_members_list(db: Session, group: str) -> Optional[Members]:
    return db.exec(select(Members).where(Group.name == group))


def get_note(db: Session, note_id: str) -> Optional[Note]:
    return db.exec(select(Note).where(Note.id == note_id)).first()


def create_activity_to_send_from_note(db_note) -> Dict[str, Any]:
    to = []
    cc = []
    for recipient in db_note.recipients:
        if recipient.type == RecipientType.to:
            to.append(recipient.url)
        elif recipient.type == RecipientType.cc:
            cc.append(recipient.url)

    note_url_id = SERVER_URL + "/note/" + str(db_note.id)
    create_id = note_url_id + "/" + uuid.uuid4().hex

    date_time_str = datetime_str(db_note.created_at)

    activity = {
        "@context": "https://www.w3.org/ns/activitystreams",
        "type": "Create",
        "id": create_id,
        "actor": get_actor_url(db_note.actor.name),
        "object": {
                "id": note_url_id,
                "type": "Note",
                "attributedTo": get_actor_url(db_note.attributed.name),
                "content": db_note.content,
                "source": db_note.source,
                "published": date_time_str,
                "to": to,
                "cc": cc
        },
        "published": date_time_str,
        "to": to,
        "cc": cc
    }
    return activity

def create_activity_to_send_from_boost(db_boost) -> Dict[str, Any]:
    to = []
    cc = []
    actor = get_actor_url(db_boost.actor.name)
    for recipient in db_boost.recipients:
        if recipient.type == RecipientType.to:
            to.append(recipient.url)
        elif recipient.type == RecipientType.cc:
            cc.append(recipient.url)

    boost_url_id = SERVER_URL + "/boost/" + str(db_boost.id)
    create_id = actor + "/" + uuid.uuid4().hex

    date_time_str = datetime_str(db_boost.created_at)

    activity = {
   "@context":[
      "https://www.w3.org/ns/activitystreams",
      {
         "@language":"und"
      }
   ],
   "actor": actor,
   "bto":[
      
   ],
   "cc":[
      
   ],
   "id": create_id,
   "object": db_boost.note_id,
   "published": date_time_str,
   "to": to,
   "cc": cc,
   "type":"Announce"
    }
    return activity