# Fedigroup

Groups in Fediverse

Trying to implement: https://github.com/yuforium/activitypub-docs

I saw this and thought it was cool: https://github.com/wmurphyrd/guppe
But I want to have also a way to search back in groups. For now I am aiming for public only groups.

Code contribution would be appreciated!

## Requirements
1. You need [nginx-proxy](https://github.com/nginx-proxy/nginx-proxy) set up, or adapt to another reverse proxy.
2. a domain
3. docker and docker-compose

## How to set up
1. 
```bash
git clone https://github.com/guysoft/fedigroup.git
cd fedigroup
cp src/docker-compose.yml.example src/docker-compose.yml
cp src/config.yml.example src/config.yml
```
2. 

3. update the values in ``docker-compose.yml`` and ``config.yml``
```
sudo docker-compose up -d
```

enjoy

## Attribution

Profile art from: https://openclipart.org/detail/169150/group-icons
