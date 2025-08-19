#!/usr/bin/python
# Python
import configparser
import hashlib
import logging
from datetime import datetime

import pytz
import sys

# Libraries
import requests

# Local
import lifestream

Lifestream = lifestream.Lifestream()
logger = logging.getLogger("Planetside2")
args = lifestream.arguments.parse_args()

IMG = "http://art.istic.net/iconography/games/planetside2.png"

def run_import():
    characters = lifestream.config.get("planetside", "characters")
    characters = characters.split(",")

    try:
        api_key = "s:{}".format(lifestream.config.get("planetside", "service_key"))
    except configparser.NoOptionError:
        api_key = ""

    url_base = "https://census.daybreakgames.com"

    api_base = "{}/{}/get/ps2:v2".format(url_base, api_key)

    image_base = url_base

    Lifestream = lifestream.Lifestream()


    for character_name in characters:
        logger.info("Data for {}".format(character_name))

        logger.info(
            "{}/character/?name.first_lower={}&c:resolve=faction".format(
                api_base, character_name
            )
        )
        charac = requests.get(
            "{}/character/?name.first_lower={}&c:resolve=faction".format(
                api_base, character_name
            )
        )

        character = charac.json()

        character_id = character["character_list"][0]["character_id"]

        profile = character["character_list"][0]

        br = profile["battle_rank"]
        faction_id = profile["faction_id"]
        faction = profile["faction"]["code_tag"].lower()
        character_name = name = profile["name"]["first"]

        ##
        ranki = requests.get(
            "{}/experience_rank?rank={}".format(api_base, br["value"]))

        rank = ranki.json()["experience_rank_list"][0][faction]["title"]["en"]
        text = "In Planetside 2, {} achieved the rank {}".format(name, rank)
        url = "https://players.planetside2.com/#!/{}".format(character_id)

        image_key = "{}_image_path".format(faction)
        image = image_base + ranki.json()["experience_rank_list"][0][image_key]

        id = hashlib.md5()
        id.update(text.encode("utf-8"))

        logger.info(text)

        Lifestream.add_entry(
            "gaming",
            id.hexdigest(),
            text,
            "Planetside 2",
            datetime.now(),
            url=url,
            image=image,
            fulldata_json=character,
        )

        # Achivements

        achievements = requests.get(
            "{}/characters_achievement/?character_id={}&c:join=achievement&c:limit=100".format(
                api_base, character_id
            )
        )

        for achievement in achievements.json()["characters_achievement_list"]:
            if achievement["finish"] == "0":
                continue

            name = achievement["achievement_id_join_achievement"]["name"]["en"]
            text = "{} earnt {}".format(character_name, name)
            image = (
                image_base +
                achievement["achievement_id_join_achievement"]["image_path"]
            )
            date = achievement["finish_date"]
            id = hashlib.md5()
            id.update(str(text + date).encode("utf-8"))

            logger.info(text)

            epoch = float(achievement["finish"])
            localzone = pytz.timezone("Europe/London")
            localtime = localzone.localize(datetime.fromtimestamp(epoch))
            utcdate = localtime.strftime("%Y-%m-%d %H:%M")

            Lifestream.add_entry(
                "gaming",
                id.hexdigest(),
                text,
                "PS2 Achivement",
                date,
                url=url,
                image=image,
                fulldata_json=achievement,
            )

def main():
    try:
        run_import()
    except Exception as e:
        ttl = Lifestream.warned_recently("planetside:exception:warning_sent")
        if ttl:
            logger.warning("Error fetching achievements: {}".format(e))
            logger.info(
                "Error already sent {} ago".format(
                    lifestream.niceTimeDelta(ttl))
            )
        else:
            logger.error("Error fetching achievements: {}".format(e))
        sys.exit(1)


if __name__ == "__main__":
    main()