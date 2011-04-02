#!/usr/bin/python

import lifestream

import dateutil.parser
import pytz
import feedparser
import datetime
import sys

if (len(sys.argv) < 2):
	print "Usage: lastfm lastfmid"
	sys.exit(5)

dbcxn  = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)

id = sys.argv[1]
url = "http://ws.audioscrobbler.com/1.0/user/%s/recenttracks.rss" % id
fp = feedparser.parse(url)
type = "lastfm"

s_sql = u'replace into lifestream (`id`, `type`, `systemid`, `title`, `date_created`, `url` ) values (0, %s, %s, %s, %s, %s);'

for i in range(1,len(fp['entries'])):
  o_item = fp['entries'][i]
  id = o_item['guid']
  title = o_item.title.encode("utf_8")
  localdate = dateutil.parser.parse(o_item.updated)
  updated = localdate.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")
  
  cursor.execute(s_sql, (type, id, title, updated, o_item['link']))
