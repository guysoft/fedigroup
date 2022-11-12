#!/usr/bin/env python3
import typer

from app.send_group import group_message as fedigroup_message

from app.common import SERVER_URL, multi_urljoin

app = typer.Typer()


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

    




if __name__ == "__main__":
    app()
