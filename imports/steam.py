#!/usr/bin/python
# Python
from xml.dom import minidom
import hashlib
import os
import pytz
from xml.parsers.expat import ExpatError
from datetime import datetime
import logging
import requests
from io import BytesIO
from pprint import pprint

# Libraries

# Local
import lifestream

logger = logging.getLogger('Steam')


lifestream.arguments.add_argument(
    '--catchup',
    required=False,
    help="Get all achievements, not just last fortnight",
    default=False,
    action='store_true')


args = lifestream.arguments.parse_args()

Lifestream = lifestream.Lifestream()

steamtime = pytz.timezone('US/Pacific')

user = lifestream.config.get("steam", "username")

logger.info(
    "Opening https://steamcommunity.com/id/%s/games?tab=recent&xml=1" %
    user)

try:
    gameslist_xml = requests.get(
        "https://steamcommunity.com/id/%s/games?tab=recent&xml=1" %
        user)
except IOError:
    #print >> sys.stderr, "Got socket error fetching games list"
    os._exit(5)

games = minidom.parse(BytesIO(gameslist_xml.content))

gamesList = games.getElementsByTagName('game')

maxGames = 10000
thisGame = 0
foundGames = 0

# for game in gameslist:
while (foundGames < maxGames and thisGame != len(gamesList)):

    # Get the current game
    game = gamesList[thisGame]

    # Iterate Loop counter to get the next game next time
    thisGame = thisGame + 1

    statspage = game.getElementsByTagName('statsLink')
    gamename = game.getElementsByTagName('name')[0].firstChild.data

    hoursFortnight = game.getElementsByTagName('hoursLast2Weeks')
    hoursEver = game.getElementsByTagName('hoursOnRecord')

    logger.info("% 3d % 3d %s" % (foundGames, thisGame, gamename))

    if len(statspage) == 0:
        logger.info("       + Skipping %s (No stats page)" % gamename)
        continue

    if not hoursEver:
        logger.info("       + Skipping %s (Not played)" % gamename)
        continue

    if not args.catchup and not hoursFortnight:
        logger.info("       + Skipping %s (Not in last fortnight)" % gamename)
        continue

    # If we found a statspage, carry on. Iterate foundGames

    foundGames = foundGames + 1

    statspage = game.getElementsByTagName('statsLink')[0].firstChild.data
    statspagexml = "%s?xml=1" % statspage

    try:
        logger.info("       + Getting Stats: %s" % statspagexml)
        response = requests.get(statspagexml)
        game = minidom.parse(BytesIO(response.content))
    except IOError:
        logger.info(
            "       + Got socket error fetching %s achievement list" %
            gamename)
        continue
    except ExpatError:
        logger.info("       + XML Error reading file. Not a real stats page.")
        continue

    for achievement in game.getElementsByTagName("achievement"):
        closed = achievement.getAttribute("closed")
        if not achievement.getElementsByTagName('name')[0].firstChild:
            logger.info("         +  (Empty Name)")
            continue

        name = achievement.getElementsByTagName('name')[0].firstChild.data
        if closed == '0':
            logger.info("         + %s (Not Achieved)" % name)
            continue

        m = hashlib.md5()

        image = achievement.getElementsByTagName(
            'iconClosed')[0].firstChild.data

        try:
            unlocked = achievement.getElementsByTagName(
                'unlockTimestamp')[0].firstChild.data
            us_timestamp = datetime.fromtimestamp(int(unlocked))
            local_timestamp = steamtime.localize(us_timestamp)
        except IndexError:
            local_timestamp = datetime.now()

        logger.info(
            "         + %s (Achieved at %s )" %
            (name, local_timestamp))

        message = "%s &ndash; %s" % (gamename, name)

        m.update(gamename.encode('utf-8'))
        m.update(name.encode('utf-8'))
        id = image

        Lifestream.add_entry(
            "achievement",
            id,
            message,
            "steam",
            local_timestamp,
            url=statspage,
            image=image)
