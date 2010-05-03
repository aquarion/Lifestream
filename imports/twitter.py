#!/usr/bin/python

import codecs, sys, os
import ConfigParser, MySQLdb, socket

import re

from datetime import datetime

from twitter import Twitter
import calendar, rfc822

from urllib2 import URLError


sys.stdout = codecs.getwriter('utf8')(sys.stdout)

basedir = os.path.dirname(os.path.abspath(sys.argv[0]))
config = ConfigParser.ConfigParser()
config.readfp(open(basedir+'/../dbconfig.ini'))
db = {}


for item in config.items("database"):
	db[item[0]] = item[1]

dbcxn = MySQLdb.connect(user = db['username'], passwd = db['password'], db = db['database'], host = db['hostname'])
cursor = dbcxn.cursor()

if (len(sys.argv) < 4):
	print "Usage: lifestreamit class username password"
	sys.exit(5)

type = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

twitter = Twitter(username, password)

try:
	tweets = twitter.statuses.user_timeline()
except ValueError:
	sys.exit(4)
except URLError, e:
	if not e.reason[0] == 104:
		print e.reason
	sys.exit(5)
#print '-- Welcome to Twipistula'

s_sql = u'replace into lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`) values (%s, %s, %s, %s, %s, %s);'

for i in range(len(tweets)):
	tweet = tweets[i]
	
	id = tweet['id']
	#message = tweet['text'].replace('"', '\\"');
	message = tweet['text'].encode("utf_8")
	source = tweet['source'];

	source = re.sub(r'<[^>]*?>', '', source) 
	
	epoch = calendar.timegm(rfc822.parsedate(tweet['created_at']));
	timestamp = datetime.fromtimestamp(epoch).isoformat();

	url = "http://twitter.com/%s/status/%d" % (username, id)

	cursor.execute(s_sql, (type, id, message, timestamp, url, source))
