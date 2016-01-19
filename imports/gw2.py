#!/usr/bin/python
# Python
import sys
import hashlib
from datetime import datetime
import logging

# Libraries
from guildwars2api.client import GuildWars2API

# Local
import lifestream


Lifestream = lifestream.Lifestream()

APIKEY = Lifestream.config.get("guildwars2", "apikey")

logger = logging.getLogger('GW2')
args = lifestream.arguments.parse_args()

api = GuildWars2API(api_version=v2)

for achivement in achivements:
    logger.info(text)

    id = hashlib.md5()
    id.update(text)
    Lifestream.add_entry(
        "gaming",
        id.hexdigest(),
        text,
        "The Secret World",
        datetime.now(),
        url=url,
        image=src)
