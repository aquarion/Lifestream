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

Lifestream = lifestream.Lifestream()

fp = feedparser.parse(url)

for i in range(len(fp['entries'])):
	o_item   = fp['entries'][i]
	id       = o_item['guid']
	dt       = datetime.fromtimestamp(mktime(o_item['updated_parsed']))
	updated  = dt.strftime("%Y-%m-%d %H:%M")
		
	Lifestream.add_entry(type=type, id=id, title=o_item['title'], source=type, date=updated, url=o_item['links'][0]['href'], fulldata_json=o_item)
