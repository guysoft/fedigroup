"""CREATE, READ, UPDATE and DELETE in the database

    Returns:
        _type_: _description_
"""
from typing import List, Optional, Dict, Any
import copy
from datetime import datetime
import uuid
from sqlmodel import select, Session
from app.schemas import GroupCreate, MemberCreateRemove, ActorCreateRemove, OauthAppCreateRemove,\
 NoteCreate, BoostCreate
from app.db import Group, Members, Actor, Note, Boost, RecipientType, NoteRecipients, BoostRecipients, \
OauthApp, OauthCode
from app.common import SERVER_URL, datetime_str

from app.get_federated_data import get_profile, actor_to_address_format, get_actor_url
from app.mastodonapi import register_oauth_application, generate_oauth_state

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


def create_recipients_list(db, recipients: List[str], recipients_type: RecipientType) -> List[NoteRecipients]:
    print("create_recipients_list")
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


def create_boost_recipients_list(db, recipients: List[str], recipients_type: RecipientType) -> List[BoostRecipients]:
    print("create_recipients_list")
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

def create_internal_note(db: Session, item: NoteCreate) -> Note:
    item["created_at"] = datetime.utcnow()

    cc = create_recipients_list(db, item["cc"], RecipientType.cc)
    to = create_recipients_list(db, item["to"], RecipientType.to)

    item["recipients"] = cc + to
    db_note_item = Note(**item)

    db.add(db_note_item)
    db.commit()
    db.refresh(db_note_item)
    return db_note_item

def create_federated_note(db: Session, item: NoteCreate) -> Note:
    cc = create_recipients_list(db, item["cc"], RecipientType.cc)
    to = create_recipients_list(db, item["to"], RecipientType.to)
    item["recipients"] = cc + to

    item = copy.copy(item)

    if "attributedTo" not in item.keys():
        return
    
    if "actor" not in item.keys():
        item["actor"] = item["attributedTo"]

    for key in ["content", "source", "summary"]:
        if key not in item.keys():
            item[key] = ""

    if type(item["actor"]) == str:
        item["actor"] = get_handle_from_url_or_create(db, item["actor"])

    if type(item["attributedTo"]) == str:
        item["attributed"] = get_handle_from_url_or_create(db, item["attributedTo"])

    db_note_item = Note(**item)

    db.add(db_note_item)
    db.commit()
    db.refresh(db_note_item)
    return db_note_item

def create_boost(db: Session, item: BoostCreate) -> Boost:
    item["created_at"] = datetime.utcnow()

    cc = create_boost_recipients_list(db, item["cc"], RecipientType.cc)
    to = create_boost_recipients_list(db, item["to"], RecipientType.to)

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

def add_oauth_secret(db: Session, item: OauthAppCreateRemove) -> OauthApp:
    db_item = OauthApp(**item)
    db.add(db_item)
    db.commit()
    db.refresh(db_item)
    return db_item

def get_actor_or_create(db: Session, actor_handle: str) -> Actor:
    """
    The get_actor_or_create function takes in a database session and an actor@server format.
    It then checks if the actor exists in the database, and if it does not, creates a new entry for that actor.
    The function returns either the existing or newly created Actor object.
    
    :param db:Session: Used to Connect to the database.
    :param actor_handle:str: Used to Get the actor if it exists.
    :return: A db actor
    
    """
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

def member_in_group(db: Session, group_name: str, actor: Actor) -> bool:
    # Check if exists:
    member_in_group = db.exec(select(Members, Group).where(
        Group.name == group_name).where(Members.member_id == actor.id)).first()

    return member_in_group is not None
        


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
        print(f'Error, group does not exist: {item["group"]}')
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


def get_note_by_object_id(db: Session, note_id: str) -> Optional[Note]:
    return db.exec(select(Note).where(Note.id == note_id)).first()


def get_boost_by_note_id(db: Session, note_id: str) -> Optional[Boost]:
    return db.exec(select(Boost).where(Boost.note_id == note_id)).first()


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

def get_domain_app_id_or_create(db: Session, domain: str, scopes: List[str]) -> OauthApp:
    scops = sorted(scopes)
    # Get oauth_secret if exists
    oauth_secret = db.exec(select(OauthApp).where(OauthApp.domain == domain).where(OauthApp.scopes == scopes)).first()

    if oauth_secret is None:
        client_id, client_secret = register_oauth_application(domain, scopes)

        oauth_secret_entry = {
            "domain": domain,
            "client_id": client_id,
            "client_secret": client_secret,
            "scopes": scopes,
        }
        oauth_secret = add_oauth_secret(db=db, item=oauth_secret_entry)
    return oauth_secret

def add_initial_oauth_code(db: Session, scopes: List[str], user: str, oauth_app: OauthApp) -> OauthCode:
    state = generate_oauth_state()

    actor_handle = f"{user}@{oauth_app.domain}"
    actor = get_actor_or_create(db, actor_handle)
    oauth_code = db.exec(select(OauthCode).where(OauthCode.actor_id == actor.id).where(OauthApp.scopes == scopes)).first()

    if oauth_code is None:
        item = {
            "oauth_app_id": oauth_app.id,
            "actor_id": actor.id,
            "state": state
        }
        oauth_code = OauthCode(**item)
        db.add(oauth_code)
        db.commit()
        db.refresh(oauth_code)
    else:
        oauth_code.oauth_app_id = oauth_app.id
        oauth_code.actor_id = actor.id
        oauth_code.state = state
        oauth_code.code = None
        db.commit()
        db.refresh(oauth_code)
    return oauth_code

def update_oauth_code(db: Session, state: str, code: str):
    oauth_code = db.exec(select(OauthCode).where(OauthCode.state == state).where(OauthCode.code == None)).first()

    if oauth_code is not None:
        oauth_code.code = code
        db.commit()
        db.refresh(oauth_code)
        return oauth_code
    return
