#!/usr/bin/python

import feedparser, urlparse
import codecs, sys, datetime,time
sys.stdout = codecs.getwriter('utf8')(sys.stdout)


if (len(sys.argv) < 2):
	print "Usage: lastfm lastfmid"
	sys.exit(5)

id = sys.argv[1]

url = "http://ws.audioscrobbler.com/1.0/user/%s/recenttracks.rss" % id

fp = feedparser.parse(url)

#print '-- Welcome to Twipistula'

type = "lastfm"

s_sql = u'replace into lifestream (`id`, `type`, `systemid`, `title`, `date_created`, `url` ) values (0, "%s", "%s", "%s", "%s", "%s");'

for i in range(len(fp['entries'])):
	o_item = fp['entries'][i]

	id = o_item['guid']

	updated = datetime.datetime.fromtimestamp(time.mktime(o_item.updated_parsed)).strftime("%Y-%m-%d %H:%M");

	title = o_item.title.replace('"', '\\"')
	#message = o_item.title.replace('"', '\\"');
	print s_sql % (type, id, title, updated, o_item['link'])
