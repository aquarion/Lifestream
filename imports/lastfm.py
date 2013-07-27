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

Lifestream = lifestream.Lifestream()

id = sys.argv[1]
url = "http://ws.audioscrobbler.com/1.0/user/%s/recenttracks.rss" % id
fp = feedparser.parse(url)
type = "lastfm"

for i in range(1,len(fp['entries'])):
  o_item = fp['entries'][i]
  id = o_item['guid']
  title = o_item.title#.encode("utf_8")
  localdate = dateutil.parser.parse(o_item.updated)
  updated = localdate.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")
  del o_item['updated_parsed']
  Lifestream.add_entry(type, id, title, "lastfm", updated, url=o_item['link'], fulldata_json=o_item)