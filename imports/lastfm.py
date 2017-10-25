#!/usr/bin/python
# Python
import dateutil.parser
import pytz
import feedparser
import sys
import logging

# Libraries

# Local
import lifestream


logger = logging.getLogger('Last.FM')
args = lifestream.arguments.parse_args()


try:
    id = lifestream.config.get("lastfm", "username")
except:
    id = False

if not id:
    logger.error("No Last.fm user found in config file")
    sys.exit(5)

Lifestream = lifestream.Lifestream()

url = "http://ws.audioscrobbler.com/1.0/user/%s/recenttracks.rss" % id
logging.info('Grabbing %s' % url)
fp = feedparser.parse(url)
type = "lastfm"

for i in range(1, len(fp['entries'])):
    o_item = fp['entries'][i]
    id = o_item['guid']
    title = o_item.title  # .encode("utf_8")
    localdate = dateutil.parser.parse(o_item.updated)
    updated = localdate.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")
    del o_item['published_parsed']
    logger.info(title)
    Lifestream.add_entry(
        type,
        id,
        title,
        "lastfm",
        updated,
        url=o_item['link'],
        fulldata_json=o_item)
