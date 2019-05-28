#!/usr/bin/python
# Python
from datetime import datetime
import logging
import requests

# Libraries
from guildwars2api.v2 import GuildWars2API

# Local
import lifestream


Lifestream = lifestream.Lifestream()

APIKEY = Lifestream.config.get("guildwars2", "apikey")

logger = logging.getLogger('GW2')
args = lifestream.arguments.parse_args()

api = GuildWars2API(
    user_agent="Lifestream <nicholas@istic.net>",
    api_key=APIKEY)

my_achivements = api.account_achievements.get()

fetch_list = []

achivements_library = {}

for achivement in my_achivements:
    if achivement[u'done']:
        ident = achivement['id']
        fetch_list.append(ident)
        achivements_library[ident] = {}
        achivements_library[ident]['progress'] = achivement

response = api.achievements.get(ids=fetch_list)

for achivement in response:
    ident = achivement['id']
    achivements_library[ident]['info'] = achivement

category_list = requests.get(
    "https://api.guildwars2.com/v2/achievements/categories/").json()
category_data = {"ids": ','.join(str(x) for x in category_list)}
category_fetch = requests.get(
    "https://api.guildwars2.com/v2/achievements/categories",
    data=category_data).json()

for category in category_fetch:
    for achivement_id in category['achievements']:
        if achivement_id in achivements_library:
            achivements_library[achivement_id]['category'] = category

for ident, achivement in achivements_library.iteritems():
    if not 'info' in achivement:
        continue

    icon = False
    if 'icon' in achivement['info']:
        icon = achivement['info']['icon']
    elif "category" in achivement:
        icon = achivement['category']['icon']
    else:
        icon = "https://wiki.guildwars2.com/images/d/d9/Retired_Achievements.png"

    if not icon:
        logger.warn(achivement['info']['name'], " - has no icon")

    text = achivement['info']['name'] + " &ndash; " + \
        achivement['info']['requirement']

#     id = hashlib.md5()
# id.update(text)
    Lifestream.add_entry(
        "achivement",
        ident,
        text,
        "Guild Wars 2",
        datetime.now(),
        image=icon)
