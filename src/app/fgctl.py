#!/usr/bin/env python3
import typer

from app.send_group import fedigroup_message, fedigroup_boost

from app.common import SERVER_URL, multi_urljoin

app = typer.Typer(pretty_exceptions_enable=False)


from app.db import SessionLocal, database

@app.command()
def group_message(group: str, message: str):
    print(group, message)

    db = SessionLocal()
    database.connect()

    preshared_key_id = multi_urljoin(SERVER_URL, "group", group) + "#main-key"
    key_path = "/data/default_gpg_key/id_rsa"

    fedigroup_message(db, group, message, preshared_key_id, key_path)
    db.close()
    database.disconnect()

@app.command()
def boost_message(group: str, note_id: str):
    print(group, note_id)

    db = SessionLocal()
    database.connect()

    preshared_key_id = multi_urljoin(SERVER_URL, "group", group) + "#main-key"
    key_path = "/data/default_gpg_key/id_rsa"

    fedigroup_boost(db, group, note_id, preshared_key_id, key_path)
    db.close()
    database.disconnect()




if __name__ == "__main__":
    app()
