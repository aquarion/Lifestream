#!/usr/bin/python

import lifestream
import dateutil.parser
import pytz

import sys, os
import re

from datetime import datetime

from twitter import Twitter

from twitter.oauth import OAuth, write_token_file, read_token_file
from twitter.oauth_dance import oauth_dance

import calendar, rfc822

from urllib2 import URLError


if (len(sys.argv) < 3):
	print "Usage: lifestreamit class username"
	sys.exit(5)

type            = sys.argv[1]
username        = sys.argv[2]

dbcxn           = lifestream.getDatabaseConnection()
cursor          = lifestream.cursor(dbcxn)

OAUTH_FILENAME  = os.environ.get('HOME', '') + os.sep + '.lifesteam_oauth_'+username
CONSUMER_KEY    = lifestream.config.get("twitter", "consumer_key")
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
	api_version='1',
	domain='api.twitter.com')


try:
	tweets = twitter.statuses.user_timeline()
except ValueError:
	sys.exit(4)
except URLError, e:
	if not e.reason[0] == 104:
		print "Caught error %s" % e.reason[0]
		print e.reason
	sys.exit(5)
except Exception, e:
	#print "Caught error %s" % Exception
	#print e
	sys.exit(12)
#print '-- Welcome to Twipistula'

s_sql = u'replace into lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`) values (%s, %s, %s, %s, %s, %s);'

for tweet in tweets:
	id = tweet['id']
	#message = tweet['text'].replace('"', '\\"');
	message = tweet['text'].encode("utf_8")
	source = tweet['source'];

	source = re.sub(r'<[^>]*?>', '', source) 
	
	url = "http://twitter.com/%s/status/%d" % (username, id)

	localdate = dateutil.parser.parse(tweet['created_at'])
        utcdate = localdate.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")
	cursor.execute(s_sql, (type, id, message, utcdate, url, source))
