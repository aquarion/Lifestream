#!/usr/bin/python
# Python
import hashlib
import ConfigParser
from datetime import datetime
import pytz
import logging

# Libraries
import requests

# Local
import lifestream

from pprint import pprint
import sys

logger = logging.getLogger('Planetside2')
args = lifestream.arguments.parse_args()

IMG = "http://art.istic.net/iconography/games/planetside2.png"

characters = lifestream.config.get("planetside", "characters")
characters = characters.split(",")

try:
    api_key = "/s:%s" % lifestream.config.get("planetside", "service_key")
except ConfigParser.NoOptionError:
    api_key = ''

url_base = "http://census.daybreakgames.com"

api_base = "%s/%s/get/ps2:v2" % (url_base, api_key)

image_base = url_base

Lifestream = lifestream.Lifestream()


for character_name in characters:
    logger.info("Data for %s" % character_name)
  
    charac = requests.get(
        "%s/character/?name.first_lower=%s&c:resolve=faction" %
        (api_base, character_name))


    character = charac.json()

    character_id = character['character_list'][0]['character_id']


    profile = character['character_list'][0]

    br = profile['battle_rank']
    faction_id = profile['faction_id']
    faction = profile['faction']['code_tag'].lower()
    character_name = name = profile['name']['first']

    ##
    ranki = requests.get(
        "%s/experience_rank?rank=%s" %
        (api_base, br['value']))

    rank = ranki.json()['experience_rank_list'][0][faction]['title']['en']
    text = "In Planetside 2, %s achieved the rank %s" % (name, rank)
    url = "https://players.planetside2.com/#!/%s" % character_id

    image_key = "%s_image_path" % faction
    image = image_base + ranki.json()['experience_rank_list'][0][image_key]

    id = hashlib.md5()
    id.update(text)

    logger.info(text)

    Lifestream.add_entry(
        "gaming",
        id.hexdigest(),
        text,
        "Planetside 2",
        datetime.now(),
        url=url,
        image=image,
        fulldata_json=character)

    # Achivements

    achivements = requests.get(
        "%s/characters_achievement/?character_id=%s&c:join=achievement&c:limit=100" %
        (api_base, character_id))

    for achivement in achivements.json()['characters_achievement_list']:
        if achivement['finish'] == "0":
            continue

        name = achivement['achievement_id_join_achievement']['name']['en']
        text = "%s earnt %s" % (character_name, name)
        image = image_base + \
            achivement['achievement_id_join_achievement']['image_path']
        date = achivement['finish_date']
        id = hashlib.md5()
        id.update(text + date)

        logger.info(text)

        epoch = float(achivement['finish'])
        localzone = pytz.timezone("Europe/London")
        localtime = localzone.localize(datetime.utcfromtimestamp(epoch))
        utcdate = localtime.strftime("%Y-%m-%d %H:%M")

        Lifestream.add_entry(
            "gaming",
            id.hexdigest(),
            text,
            "PS2 Achivement",
            date,
            url=url,
            image=image,
            fulldata_json=achivement)

    # if 'stats_daily' in profile.keys():
    # 	stats = profile['stats_daily']
    # 	text = "Played Planetside as %s %s for %s, with a K:D of %2.2f%% (%d:%d)"
    # 	time = lifestream.niceTimeDelta(int(stats['play_time']['value']))
    # 	kd   = float(stats['kill_death_ratio']['value'])
    # 	k    = int(stats['kills']['value'])
    # 	d    = int(stats['deaths']['value'])
    # 	text = text % (rank, name, time, kd, k, d)

    # 	id = hashlib.md5()
    # 	id.update(text)
    # 	Lifestream.add_entry("gaming", id.hexdigest(), text, "Planetside 2", datetime.now(), url=url, image=IMG, fulldata_json=stats)
