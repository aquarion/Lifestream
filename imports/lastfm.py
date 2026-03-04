#!/usr/bin/python
"""Last.fm scrobble importer for Lifestream."""

# Python
import hashlib
import logging
import sys

import dateutil.parser
import feedparser

# Local
import lifestream
import pytz
from lifestream.db import EntryStore

logger = logging.getLogger("Last.FM")


def main():
    """Import recent Last.fm scrobbles."""
    lifestream.parse_args()

    try:
        username = lifestream.config.get("lastfm", "username")
    except Exception:
        username = None

    if not username:
        logger.error("No Last.fm user found in config file")
        sys.exit(5)

    entry_store = EntryStore()

    url = f"https://xiffy.nl/lastfmrss.php?user={username}"
    logger.info("Grabbing %s", url)
    fp = feedparser.parse(url)
    item_type = "lastfm"

    for i in range(1, len(fp["entries"])):
        o_item = fp["entries"][i]

        item_id = hashlib.md5()
        item_id.update(o_item["guid"].encode("utf-8"))

        title = o_item.title
        localdate = dateutil.parser.parse(o_item.updated)
        updated = localdate.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")
        del o_item["published_parsed"]
        logger.info(title)
        entry_store.add_entry(
            item_type,
            item_id.hexdigest(),
            title,
            "lastfm",
            updated,
            url=o_item["link"],
            fulldata_json=o_item,
        )


if __name__ == "__main__":
    main()
