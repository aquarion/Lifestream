#!/usr/bin/python

import lifestream

import feedparser
import sys
from datetime import datetime
from time import mktime

if (len(sys.argv) < 3):
	print "Usage: %s type url" % sys.argv[0]
	sys.exit(5)

type = sys.argv[1]
url = sys.argv[2]

dbcxn = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)

fp = feedparser.parse(url)


s_sql = u'replace into lifestream (`type`, `systemid`, `title`, `url`, `date_created`, `source`, `image`) values (%s, %s, %s, %s, %s, "", "");'

for i in range(len(fp['entries'])):
	o_item   = fp['entries'][i]
	id       = o_item['guid']
	dt       = datetime.fromtimestamp(mktime(o_item['updated_parsed']))
	updated  = dt.strftime("%Y-%m-%d %H:%M")
	words = (o_item['summary'][:253] + '..') if len(o_item['summary']) > 255 else o_item['summary']
	cursor.execute(s_sql, (type, id, words, o_item['links'][0]['href'],  updated))
