#!/usr/bin/python

import lifestream
import dateutil.parser
import pytz

import sys
import os
import re

from datetime import datetime

from twitter import Twitter

from twitter.oauth import OAuth, write_token_file, read_token_file
from twitter.oauth_dance import oauth_dance

import calendar
import rfc822

from urllib2 import URLError

import socket

import logging

Lifestream = lifestream.Lifestream()

logger = logging.getLogger('Twitter')
args = lifestream.arguments.parse_args()


socket.setdefaulttimeout(60)  # Force a timeout if twitter doesn't respond


OAUTH_FILENAME = "%s/twitter.oauth" % (
    lifestream.config.get("global", "secrets_dir"))
CONSUMER_KEY = lifestream.config.get("twitter", "consumer_key")
CONSUMER_SECRET = lifestream.config.get("twitter", "consumer_secret")

ACCOUNTS = lifestream.config.get("twitter", "accounts")

if not ACCOUNTS:
    logger.error("No twitter accounts found in config")
    sys.exit(5)

if not os.path.exists(OAUTH_FILENAME):
    oauth_dance(
        "Lifestream", CONSUMER_KEY, CONSUMER_SECRET,
        OAUTH_FILENAME)


oauth_token, oauth_token_secret = read_token_file(OAUTH_FILENAME)

twitter = Twitter(
    auth=OAuth(
        oauth_token, oauth_token_secret, CONSUMER_KEY, CONSUMER_SECRET),
    secure=True,
    api_version='1.1',
    domain='api.twitter.com')

for account in ACCOUNTS.split(","):
    logger.debug("Loading tweets for %s" % account)
    try:
        tweets = twitter.statuses.user_timeline(screen_name=account)
    except ValueError:
        sys.exit(4)
    except URLError as e:
        if not e.reason[0] == 104:
            logger.error("Caught error %s" % e.reason[0])
            logger.error(e.reason)
        sys.exit(5)
    # except Exception as e:
    #     logger.error("Caught error %s" % Exception)
    #     logger.error(e)
    #     sys.exit(12)
    # logger.info('-- Welcome to Twipistula')

    for tweet in tweets:
        id = tweet['id']
        image = tweet['user']['profile_image_url']
        message = tweet['text'].encode("utf_8")
        source = tweet['source']
        logger.debug(" -  %s" % tweet['text'].encode("utf_8"))

        source = re.sub(r'<[^>]*?>', '', source)

        url = "http://twitter.com/%s/status/%d" % (account, id)

        localdate = dateutil.parser.parse(tweet['created_at'])
        utcdate = localdate.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")

        Lifestream.add_entry(
            "twitter",
            id,
            message,
            source,
            utcdate,
            url=url,
            image=image,
            fulldata_json=tweet)
