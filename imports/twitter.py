#!/usr/bin/python

import codecs, sys
sys.stdout = codecs.getwriter('utf8')(sys.stdout)
import re

from datetime import datetime

from twitter import Twitter
import calendar, rfc822

if (len(sys.argv) < 4):
	print "Usage: lifestreamit class username password"
	sys.exit(5)

type = sys.argv[1]
username = sys.argv[2]
password = sys.argv[3]

twitter = Twitter(username, password)

tweets = twitter.statuses.user_timeline()

#print '-- Welcome to Twipistula'

s_sql = u'replace into lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`) values ("%s", %s, "%s", "%s", "%s", "%s");'

for i in range(len(tweets)):
	tweet = tweets[i]
	
	id = tweet['id']
	message = tweet['text'].replace('"', '\\"');
	source = tweet['source'];

	source = re.sub(r'<[^>]*?>', '', source) 
	
	epoch = calendar.timegm(rfc822.parsedate(tweet['created_at']));
	timestamp = datetime.fromtimestamp(epoch).isoformat();

	url = "http://twitter.com/%s/status/%d" % (username, id)

	print s_sql % (type, id, message, timestamp, url, source)
