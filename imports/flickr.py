#!/usr/bin/python

import feedparser, urlparse
import codecs, sys
sys.stdout = codecs.getwriter('utf8')(sys.stdout)


if (len(sys.argv) < 3):
	print "Usage: flickr type ID"
	sys.exit(5)

url = "http://api.flickr.com/services/feeds/photos_public.gne?id=%s&lang=en-us&format=atom" % sys.argv[2]


fp = feedparser.parse(url)

#print '-- Welcome to Twipistula'

type = sys.argv[1]

s_sql = u'replace into lifestream (`type`, `systemid`, `title`, `url`, `date_created`) values ("%s", "%s", "%s", "%s", "%s");'

for i in range(len(fp['entries'])):
	o_item = fp['entries'][i]

	#id = kaboom[1]

	id = o_item['guid']

	#message = o_item.title.replace('"', '\\"');
	#if o_item.has_key("content"):
	#	message = o_item['content'][0]['value'].replace('"', '\\"');
	#else:
	#	message = o_item['title']+": "+o_item['description'].replace('"', '\\"');
	message = o_item['title'].replace('"', '\\"');
	print s_sql % (type, id, message, o_item['links'][0]['href'], o_item['published'])
