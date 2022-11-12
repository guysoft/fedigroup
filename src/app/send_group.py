# functions that use both crud and send federated data
from typing import Any, Dict
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from urllib.parse import urljoin
from app.crud import create_internal_note, get_handle_from_url_or_create, create_activity_to_send_from_note, get_members_list, get_group_by_name, get_actor_or_create
from app.common import SERVER_DOMAIN, SERVER_URL, multi_urljoin
from app.send_federated_data import send_signed
from app.get_federated_data import actor_to_address_format, get_actor_inbox, get_actor_url


def group_message(db: Session, group: str, message: str, preshared_key_id, key_path) -> Dict[str, Any]:
    """Send a group message to all members in group"""
    now_datetime = datetime.now(timezone.utc)

    actor = group + "@" + SERVER_DOMAIN
    note_data_dict = {
        "actor": get_actor_or_create(db, actor),
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
    send_message(db, activity, preshared_key_id, key_path)
    return


def send_message(db, activity, preshared_key_id, key_path):
    for recipient in activity["object"]["cc"]:
        start_pattern = urljoin(SERVER_URL, "group/")
        end_pattern = "/followers"
        if recipient.startswith(start_pattern) and recipient.endswith(end_pattern):
            # Not federeated its our own server
            # pattern = multi_urljoin(SERVER_URL, "group", group, "followers")
            group = recipient[len(start_pattern):-len(end_pattern)]
            
            db_group = get_group_by_name(db, group)
            inboxes = []
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
