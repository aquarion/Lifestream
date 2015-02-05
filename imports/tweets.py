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
socket.setdefaulttimeout(60) # Force a timeout if twitter doesn't respond

if (len(sys.argv) < 3):
    print "Usage: lifestreamit class username"
    sys.exit(5)

type = sys.argv[1]
username = sys.argv[2]

Lifestream = lifestream.Lifestream()

OAUTH_FILENAME = "%s/twitter_%s.oauth" % (
    lifestream.config.get("global", "secrets_dir"), username)
CONSUMER_KEY = lifestream.config.get("twitter", "consumer_key")
CONSUMER_SECRET = lifestream.config.get("twitter", "consumer_secret")

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


try:
    tweets = twitter.statuses.user_timeline()
except ValueError:
    sys.exit(4)
except URLError as e:
    if not e.reason[0] == 104:
        print "Caught error %s" % e.reason[0]
        print e.reason
    sys.exit(5)
except Exception as e:
    print "Caught error %s" % Exception
    print e
    sys.exit(12)
# print '-- Welcome to Twipistula'

for tweet in tweets:
    id = tweet['id']
    #message = tweet['text'].replace('"', '\\"');
    image = tweet['user']['profile_image_url']
    message = tweet['text'].encode("utf_8")
    source = tweet['source']

    source = re.sub(r'<[^>]*?>', '', source)

    url = "http://twitter.com/%s/status/%d" % (username, id)

    localdate = dateutil.parser.parse(tweet['created_at'])
    utcdate = localdate.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")
    Lifestream.add_entry(
        type,
        id,
        message,
        source,
        utcdate,
        url=url,
        image=image,
        fulldata_json=tweet)
