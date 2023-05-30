# Fedigroup

Groups in the Fediverse

Fegigroup lets you create a group and then mention it in the fediverse, the group would then boost your message and also store its contents for search.
There is also a web UI that lets you search within groups you are a member of (search is currently being implemented).

The server is currently in alpha stage and many critical features don't work yet. Contributions are welcome!

### Features

* You can login using a Mastodon-API supported account and create a group
* You can follow that group and it will boost mentions of it to other people.
* The group stores the message in the database

### What does not work yet
* Search
* Pagination
* Attachment save/displa
* Posting from within the webui
* Like/share from within the webui
* Delete activity
* Edit acttivity
* Edit existing group
* Delete / archive group
* Moderation (delete/block/defedate)

### General info
* All groups are public

## Motivation
I was trying to implement: https://github.com/yuforium/activitypub-docs
or: https://codeberg.org/fediverse/fep/src/branch/main/feps/fep-1b12.md
While being functional

I saw this and thought it was cool: https://github.com/wmurphyrd/guppe
But I want to have also a way to search back in groups.

Code contribution would be appreciated!

## Requirements
1. You need [nginx-proxy](https://github.com/nginx-proxy/nginx-proxy) set up, or adapt to another reverse proxy.
2. a domain
3. docker and docker-compose (or docker-compose)

## How to set up
1. 
```bash
git clone https://github.com/guysoft/fedigroup.git
cd fedigroup
cp src/docker-compose.yml.example src/docker-compose.yml
cp src/config.yml.example src/config.yml
```

2. update the values in ``docker-compose.yml`` and ``config.yml``
```
sudo docker compose up -d
```
3. Run database migrations
```
sudo docker compose exec fedigroup alembic upgrade head
```
4. restart docker
```
sudo docker compose stop
sudo docker compose start
```

enjoy

## Attribution

Profile art from: https://openclipart.org/detail/169150/group-icons
