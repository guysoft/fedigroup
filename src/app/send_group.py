# functions that use both crud and send federated data
from typing import Any, Dict, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from urllib.parse import urljoin
from app.crud import (
    create_internal_note,
    get_handle_from_url_or_create,
    create_activity_to_send_from_note,
    create_activity_to_send_from_boost,
    get_members_list, get_group_by_name,
    get_actor_or_create, create_boost,
    create_federated_note,
    member_in_group,
    get_boost_by_note_id
)
from app.common import SERVER_DOMAIN, SERVER_URL, multi_urljoin, is_local_actor, get_handle_name, get_server_keys
from app.send_federated_data import send_signed
from app.get_federated_data import actor_to_address_format, get_actor_inbox, get_actor_url
from app.schemas import NoteCreate

def fedigroup_message(db: Session, group: str, message: str, preshared_key_id, key_path) -> Dict[str, Any]:
    """Send a group message to all members in group"""
    now_datetime = datetime.now(timezone.utc)

    actor = group + "@" + SERVER_DOMAIN
    note_data_dict = {
        "group": get_group_by_name(db, group),
        "attributed": get_actor_or_create(db, actor),
        "content": message,
        "source": message,
        "summary": "",
        "created_at": now_datetime,
        "sensitive": False,
        "to": [],
        "cc": [multi_urljoin(SERVER_URL, "group", group, "followers"),
        "https://www.w3.org/ns/activitystreams#Public"
        ]
    }

    note_create = create_internal_note(db, note_data_dict)

    activity = create_activity_to_send_from_note(note_create)
    send_message(db, activity, preshared_key_id, key_path, activity["object"]["cc"])
    return

def fedigroup_boost(db: Session, group: str, note_id: str, preshared_key_id, key_path) -> Dict[str, Any]:
    """Boost a message in a group"""
    now_datetime = datetime.now(timezone.utc)
    
    actor = group + "@" + SERVER_DOMAIN
    boost_data_dict = {
        "group": get_group_by_name(db, group),
        "attributed": get_actor_or_create(db, actor),
        "created_at": now_datetime,
        "note_id": note_id,
        "sensitive": False,
        "to": [multi_urljoin(SERVER_URL, "group", group, "followers"),
        "https://www.w3.org/ns/activitystreams#Public"
        ],
        "cc": []
    }

    boost_create = create_boost(db, boost_data_dict)

    activity = create_activity_to_send_from_boost(boost_create)
    send_message(db, activity, preshared_key_id, key_path, activity["to"])
    return


def save_message_and_boost(db: Session, item: Dict[str, Any], groups: List[str]):
    # Make sure user is a member of a group
    author_actor_url = item["attributedTo"]
    author_of_note = get_actor_or_create(db, actor_to_address_format(author_actor_url))
    note_id = item["id"]

    print(f"note_id: {note_id}")

    for group in groups:
        print(f"boosting test group: {group}")
        actor = group + "@" + SERVER_DOMAIN
        group_db = get_group_by_name(db, group)
        in_reply_to = item.get("inReplyTo", None)
        replied_to_existing_topic = in_reply_to is not None and get_boost_by_note_id(db, in_reply_to) is not None
        is_member_in_group = member_in_group(db, group, author_of_note)

        if is_member_in_group or replied_to_existing_topic:
            if replied_to_existing_topic and not is_member_in_group:
                print("Replied to existing topic, posting for non-member")
            now_datetime = datetime.now(timezone.utc)
            boost_data_dict = {
                "group": group_db,
                "attributed": get_actor_or_create(db, actor),
                "created_at": now_datetime,
                "note_id": note_id,
                "sensitive": False,
                "to": [multi_urljoin(SERVER_URL, "group", group, "followers"),
                "https://www.w3.org/ns/activitystreams#Public"
                ],
                "cc": []
                }
            
            boost = create_boost(db, boost_data_dict)
            activity = create_activity_to_send_from_boost(boost)
            preshared_key_id, key_path = get_server_keys(group)
            send_message(db, activity, preshared_key_id, key_path, activity["to"])
        else:
            print(f"Author or note {author_of_note.name} is not a member of group {group}, not boosting")
    return


def send_message(db, activity, preshared_key_id, key_path, recipients):
    inboxes = []
    for recipient in recipients:
        start_pattern = urljoin(SERVER_URL, "group/")
        end_pattern = "/followers"
        if recipient.startswith(start_pattern) and recipient.endswith(end_pattern):
            # Not federeated its our own server
            # pattern = multi_urljoin(SERVER_URL, "group", group, "followers")
            group = recipient[len(start_pattern):-len(end_pattern)]
            
            db_group = get_group_by_name(db, group)
            
            if db_group is not None:
                members = db_group.members
            
                for member in members:
                    actor_inbox = get_actor_inbox(get_actor_url(member.member.name), shared=True)
                    if actor_inbox not in inboxes:
                        inboxes.append(actor_inbox)

    send_signed_multi(activity, inboxes, preshared_key_id, key_path)

    
def send_signed_multi(activity, inboxes, preshared_key_id, key_path):
    # TODO: Make this a worker
    for inbox in inboxes:
        print("Sending to: " + str(inbox))
        send_signed(inbox, activity, preshared_key_id, key_path)    
    return
