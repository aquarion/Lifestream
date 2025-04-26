#!/usr/bin/python
# Python
import logging
import sys
from datetime import datetime, timedelta

import requests
from guildwars2api.base import GuildWars2APIError
# Libraries
from guildwars2api.v2 import GuildWars2API

# Local
import lifestream

Lifestream = lifestream.Lifestream()

APIKEY = Lifestream.config.get("guildwars2", "apikey")

logger = logging.getLogger("GW2")
args = lifestream.arguments.parse_args()

api = GuildWars2API(user_agent="Lifestream <nicholas@istic.net>", api_key=APIKEY)


@Lifestream.cache_this("gw2.categories", 86400)
def get_categories():
    category_list = requests.get(
        "https://api.guildwars2.com/v2/achievements/categories/"
    ).json()

    category_fetch = []

    step = 200
    for i in range(0, len(category_list), step):
        logger.debug(
            "Fetching Category {} to {} of {}".format(i, i + step, len(category_list))
        )

        category_data = {"ids": ",".join(str(x) for x in category_list[i : i + step])}
        category_request = requests.get(
            "https://api.guildwars2.com/v2/achievements/categories", data=category_data
        ).json()
        category_fetch += category_request

    return category_fetch


def get_all_my_achievements(api):
    try:
        my_achievements = api.account_achievements.get()
    except GuildWars2APIError as e:

        ttl = Lifestream.warned_recently("gw2:api_error:warning_sent")
        if ttl:
            logger.warning("Error fetching achievements: {}".format(e))
            logger.info(
                "Error already sent {} ago".format(lifestream.niceTimeDelta(ttl))
            )
        else:
            logger.error("Error fetching achievements: {}".format(e))

        sys.exit(1)

    fetch_list = []

    achievements_library = {}

    for achievement in my_achievements:
        if achievement["done"]:
            ident = achievement["id"]
            fetch_list.append(ident)
            achievements_library[ident] = {}
            achievements_library[ident]["progress"] = achievement

    # Chunk

    logger.debug("Fetch list is {} long".format(len(fetch_list)))

    ach_index = 0
    ach_pagesize = 100
    list_size = len(fetch_list)

    for ach_index in range(0, list_size, ach_pagesize):
        fetch_chunk = fetch_list[ach_index : ach_index + ach_pagesize]
        logger.debug(
            "Fetching Achivement {} to {} of {}".format(
                ach_index, ach_index + ach_pagesize, len(fetch_chunk)
            )
        )

        response = api.achievements.get(ids=fetch_chunk)

        for achievement in response:
            ident = achievement["id"]
            achievements_library[ident]["info"] = achievement

    return achievements_library


achievements_library = get_all_my_achievements(api)


for category in get_categories():
    for achievement_id in category["achievements"]:
        if achievement_id in achievements_library:
            achievements_library[achievement_id]["category"] = category

for ident, achievement in achievements_library.items():
    if not "info" in achievement:
        continue

    icon = False
    if "icon" in achievement["info"]:
        icon = achievement["info"]["icon"]
    elif "category" in achievement:
        icon = achievement["category"]["icon"]
    else:
        icon = "https://wiki.guildwars2.com/images/d/d9/Retired_Achievements.png"

    if not icon:
        logger.warn(achievement["info"]["name"], " - has no icon")

    text = (
        achievement["info"]["name"] + " &ndash; " + achievement["info"]["requirement"]
    )

    logger.info(text)

    #     id = hashlib.md5()
    # id.update(text)
    Lifestream.add_entry(
        "achievement", ident, text, "Guild Wars 2", datetime.now(), image=icon
    )
