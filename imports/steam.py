#!/usr/bin/python
# Python
from xml.dom import minidom
import urllib2 as urllib
import hashlib
import os
import pytz
from xml.parsers.expat import ExpatError
from datetime import datetime
import logging

# Libraries

# Local
import lifestream

logger = logging.getLogger('Steam')
args = lifestream.arguments.parse_args()

Lifestream = lifestream.Lifestream()

steamtime = pytz.timezone('US/Pacific')

user = lifestream.config.get("steam", "username")

logger.info(
    "Opening http://steamcommunity.com/id/%s/games?tab=recent&xml=1" %
    user)

try:
    gameslist_xml = urllib.urlopen(
        "http://steamcommunity.com/id/%s/games?tab=recent&xml=1" %
        user)
except IOError:
    #print >> sys.stderr, "Got socket error fetching games list"
    os._exit(5)

games = minidom.parse(gameslist_xml)

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

    logger.info("% 3d % 3d %s" % (foundGames, thisGame, gamename))

    if len(statspage) == 0:
        logger.info("       + Skipping %s (No stats page)" % gamename)
        continue
    else:
        logger.info("       + Keeping %s" % gamename)

    # If we found a statspage, carry on. Iterate foundGames

    foundGames = foundGames + 1

    statspage = game.getElementsByTagName('statsLink')[0].firstChild.data
    statspagexml = "%s?xml=1" % statspage

    try:
        logger.info("       + Getting Stats: %s" % statspagexml)
        game = minidom.parse(urllib.urlopen(statspagexml))
    except IOError:
        logger.info(
            "       + Got socket error fetching %s achievement list" %
            gamename)
        continue
    except ExpatError:
        logger.info("       + XML Error reading file. Not a real stats page.")
        continue

    for achivement in game.getElementsByTagName("achievement"):
        closed = achivement.getAttribute("closed")
        if not achivement.getElementsByTagName('name')[0].firstChild:
            logger.info("         +  (Empty Name)")
            continue

        name = achivement.getElementsByTagName('name')[0].firstChild.data
        if closed == u'0':
            logger.info("         + %s (Not Achieved)" % name)
            continue

        m = hashlib.md5()

        image = achivement.getElementsByTagName(
            'iconClosed')[0].firstChild.data

        try:
            unlocked = achivement.getElementsByTagName(
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
            "achivement",
            id,
            message,
            "steam",
            local_timestamp,
            url=statspage,
            image=image)
