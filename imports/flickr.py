#!/usr/bin/python

import lifestream

import feedparser
import sys
import dateutil.parser


if (len(sys.argv) < 3):
	print "Usage: %s type ID" % sys.argv[0]
	sys.exit(5)

url = "http://api.flickr.com/services/feeds/photos_public.gne?id=%s&lang=en-us&format=atom" % sys.argv[2]

dbcxn  = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)

fp = feedparser.parse(url)

type = sys.argv[1]

s_sql = u'replace into lifestream (`type`, `systemid`, `title`, `url`, `date_created`, `source`, `image`) values (%s, %s, %s, %s, %s, "", %s);'

for i in range(len(fp['entries'])):
	o_item = fp['entries'][i]
	id = o_item['guid']
	result = dateutil.parser.parse( o_item['published'])
	message = o_item['title'].replace('"', '\\"');

	image = ""
	for link in o_item['links']:
		if link['rel'] == u'enclosure':
			image = link['href']

	cursor.execute(s_sql, (type, id, message, o_item['links'][0]['href'],  result, image))
