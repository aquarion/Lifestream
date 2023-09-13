#!/usr/bin/python
# Python
from datetime import datetime
import logging
import requests
import sys

# Libraries
from guildwars2api.v2 import GuildWars2API
from guildwars2api.base import GuildWars2APIError

# Local
import lifestream


Lifestream = lifestream.Lifestream()

APIKEY = Lifestream.config.get("guildwars2", "apikey")

logger = logging.getLogger('GW2')
args = lifestream.arguments.parse_args()

api = GuildWars2API(
    user_agent="Lifestream <nicholas@istic.net>",
    api_key=APIKEY)



@Lifestream.cache_this('gw2.categories', 86400)
def get_categories():
    category_list = requests.get(
        "https://api.guildwars2.com/v2/achievements/categories/").json()

    category_fetch = []

    step = 200
    for i in range(0, len(category_list), step):
        logger.debug("Fetching Category {} to {} of {}".format(i, i + step, len(category_list)))
        
        category_data = {"ids": ','.join(str(x) for x in category_list[i:i+step])}
        category_request = requests.get(
        "https://api.guildwars2.com/v2/achievements/categories",
        data=category_data).json()
        category_fetch += category_request

    return category_fetch


def get_all_my_achivements(api):
    my_achivements = api.account_achievements.get()

    fetch_list = []

    achivements_library = {}

    for achivement in my_achivements:
        if achivement['done']:
            ident = achivement['id']
            fetch_list.append(ident)
            achivements_library[ident] = {}
            achivements_library[ident]['progress'] = achivement


    # Chunk 

    logger.debug("Fetch list is {} long".format(len(fetch_list)))

    ach_index = 0
    ach_pagesize = 100
    list_size = len(fetch_list)

    for ach_index in range(0, list_size, ach_pagesize):
        fetch_chunk = fetch_list[ach_index:ach_index+ach_pagesize]
        logger.debug("Fetching Achivement {} to {} of {}".format(ach_index, ach_index + ach_pagesize, len(fetch_chunk)))

        response = api.achievements.get(ids=fetch_chunk)

        for achivement in response:
            ident = achivement['id']
            achivements_library[ident]['info'] = achivement

    return achivements_library



achivements_library = get_all_my_achivements(api)


for category in get_categories():
    for achivement_id in category['achievements']:
        if achivement_id in achivements_library:
            achivements_library[achivement_id]['category'] = category

for ident, achivement in achivements_library.items():
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
    
    logger.info(text)

#     id = hashlib.md5()
# id.update(text)
    Lifestream.add_entry(
        "achivement",
        ident,
        text,
        "Guild Wars 2",
        datetime.now(),
        image=icon)
