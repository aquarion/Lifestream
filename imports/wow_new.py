#!/usr/bin/python
# -*- coding: utf-8 -*-

# Python
import pickle
from datetime import datetime
import socket
import logging
import pytz
import hashlib
import sys
import ConfigParser  # For the exceptions

# Libraries
from battlenet.oauth2 import BattleNetOAuth2
from battlenet.community.wow.achievements import Achievement
from battlenet.community.wow.characters import Character

# Local
import lifestream
import CodeFetcher9000

from pprint import pprint

Lifestream = lifestream.Lifestream()

logger = logging.getLogger('WoW')

lifestream.arguments.add_argument(
    '--reauth',
    required=False,
    help="Get new token",
    default=False,
    action='store_true')

lifestream.arguments.add_argument(
    '--catchup',
    required=False,
    help="Force sync of all achivements",
    default=False,
    action='store_true')


args = lifestream.arguments.parse_args()


socket.setdefaulttimeout(60)  # Force a timeout if twitter doesn't respond


OAUTH_FILENAME = "%s/blizardapi.oauth" % (
    lifestream.config.get("global", "secrets_dir"))
APP_KEY = lifestream.config.get("battlenet_api", "key")
APP_SECRET = lifestream.config.get("battlenet_api", "secret")
APP_REGION = lifestream.config.get("battlenet_api", "region")


def authenticate(
        OAUTH_FILENAME,
        consumer_key,
        consumer_secret,
        region,
        force_reauth=False):

    if not force_reauth:
        try:
            f = open(OAUTH_FILENAME, "rb")
            oauth_token = pickle.load(f)
            f.close()
        except:
            logger.error("Couldn't open %s, reloading..." % OAUTH_FILENAME)
            oauth_token = False
    else:
        oauth_token = False

    try:
        CodeFetcher9000.are_we_working()
        redirect_uri = CodeFetcher9000.get_url()
        UseCodeFetcher = True
    except CodeFetcher9000.WeSayNotToday:
        try:
            redirect_uri = '{}/keyback/wow.py'.format(
                lifestream.config.get(
                    "dayze",
                    "base")),
            UseCodeFetcher = False
        except ConfigParser.Error:
            logger.error("Dayze base not configured")
            print "To catch an OAuth request, you need either CodeFetcher9000 or Dayze configured in config.ini"
            sys.exit(32)

    if oauth_token:

        expiration_date = datetime.fromtimestamp(oauth_token['expires_at'])
        if datetime.now() > expiration_date:
            print "Token has expired!"

        delta = expiration_date - datetime.now()

        if delta.days <= 7:
            print "Token will expire in {} days!".format(delta.days)

        return BattleNetOAuth2(
            key=consumer_key,
            secret=consumer_secret,
            region=region,
            # scope='sc2.profile',
            redirect_uri=redirect_uri,
            access_token=oauth_token['access_token']
        )

    bnet = BattleNetOAuth2(
        key=consumer_key,
        secret=consumer_secret,
        region=region,
        # scope='sc2.profile',
        redirect_uri=redirect_uri,
    )

    url, state = bnet.get_authorization_url()

    # Step 2: Redirect to the provider. Since this is a CLI script we do not
    # redirect. In a web application you would redirect the user to the URL
    # below.

    print "Go to the following link in your browser:"
    print url
    print

    if UseCodeFetcher:
        oauth_redirect = CodeFetcher9000.get_code("code")
        oauth_verifier = oauth_redirect['code'][0]
    else:
        print "If you configure CodeFetcher9000, this is a lot easier."
        print " - "
        oauth_verifier = raw_input('What is the PIN? ')

    data = bnet.retrieve_access_token(oauth_verifier)

    f = open(OAUTH_FILENAME, "w")
    pickle.dump(data, f)
    f.close()

    return bnet

#     return oauth_token

bnet = authenticate(
    OAUTH_FILENAME,
    APP_KEY,
    APP_SECRET,
    APP_REGION,
    args.reauth)


steamtime = pytz.timezone('Europe/Paris')

responsecode, profile = bnet.get_profile()

if not responsecode == 200:
    logging.error("Not good: %s" % profile)
    sys.exit(5)


def log_achievement(item, timestamp, character):
    image = "http://%s.media.blizzard.com/wow/icons/56/%s.jpg" % (
        APP_REGION, item['icon'])
    url = "http://%s.battle.net/wow/en/character/%s/%s/simple" % (
        APP_REGION, character['realm'], character['name'])
    # if item['accountWide']:
    #     text = "%s &mdash; %s" % (item['title'], item['description'])
    # else:
    #     text = "%s earnt %s &mdash; %s" % (character['name'], item['title'], item['description'])

    text = u"%s --- %s" % (item['title'], item['description'])

    date = datetime.fromtimestamp(timestamp / 1000)

    localdate = steamtime.localize(date)
    utcdate = localdate.astimezone(pytz.utc)

    id = hashlib.md5()
    id.update("%d-wow" % item['id'])

    logger.info(text)

    # print text, image, utcdate, item['accountWide']

    Lifestream.add_entry(
        "gaming",
        id.hexdigest(),
        text,
        "blizzard_wow",
        utcdate,
        url=url,
        image=image,
        fulldata_json=item)

for character in profile['characters']:
    # print "%s L%d %s" % (character['name'], character['level'], character['class'])
    # pprint(character)
    #Achievement( apikey='Your key', region='us',achievement="" )

    modified = datetime.fromtimestamp(character['lastModified'] / 1000)
    since_login = (datetime.now() - modified).days

    if args.catchup:

        char = Character(
            apikey=APP_KEY,
            region=APP_REGION,
            name=character['name'],
            realm=character['realm'],
            fields=['achievements'])
        status_code, character_data = char.get()

        if status_code == 404:
            logging.warning(
                "Failed to get data for %s: %s" %
                (character['name'], status_code))
            continue

        completed = character_data['achievements']['achievementsCompleted']
        completed_ts = character_data['achievements'][
            'achievementsCompletedTimestamp']
        for index in range(0, len(completed)):
            # print index, completed[index], completed_ts[index]
            status_code, achievement = Achievement(
                apikey=APP_KEY, region=APP_REGION, achievement=completed[index]).get()
            if not status_code == 200:
                logging.error("Not good: %s" % profile)
                print profile
                sys.exit(5)
            log_achievement(achievement, completed_ts[index], character)
    else:

        if since_login > 7:
            continue

        char = Character(
            apikey=APP_KEY,
            region=APP_REGION,
            name=character['name'],
            realm=character['realm'],
            fields=['feed'])
        status_code, character_data = char.get()

        if status_code == 404:
            logging.warning(
                "Failed to get data for %s: %s" %
                (character['name'], status_code))
            continue

        for item in character_data['feed']:
            if item['type'] in ('ACHIEVEMENT', 'BOSSKILL'):
                # pprint(item)
                log_achievement(
                    item['achievement'],
                    item['timestamp'],
                    character)

            elif item['type'] == u'LOOT':
                pass
            elif item['type'] == u'CRITERIA':
                pass
            else:
                pprint(item)
