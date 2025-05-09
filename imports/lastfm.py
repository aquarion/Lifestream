#!/usr/bin/python
# Python
import hashlib
import logging
import sys

import dateutil.parser
import feedparser
import pytz

# Local
import lifestream

# Libraries


logger = logging.getLogger("Last.FM")
args = lifestream.arguments.parse_args()


try:
    id = lifestream.config.get("lastfm", "username")
except:
    id = False

if not id:
    logger.error("No Last.fm user found in config file")
    sys.exit(5)

Lifestream = lifestream.Lifestream()

url = "https://xiffy.nl/lastfmrss.php?user=%s" % id
logging.info("Grabbing %s" % url)
fp = feedparser.parse(url)
type = "lastfm"

for i in range(1, len(fp["entries"])):
    o_item = fp["entries"][i]

    id = hashlib.md5()
    id.update(o_item["guid"].encode("utf-8"))

    title = o_item.title  # .encode("utf_8")
    localdate = dateutil.parser.parse(o_item.updated)
    updated = localdate.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")
    del o_item["published_parsed"]
    logger.info(title)
    Lifestream.add_entry(
        type,
        id.hexdigest(),
        title,
        "lastfm",
        updated,
        url=o_item["link"],
        fulldata_json=o_item,
    )
