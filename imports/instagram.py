# -*- coding: utf-8 -*-

import logging

# Python
import sys
from datetime import datetime
from pprint import pprint

from InstagramAPI import InstagramAPI

# Local
import lifestream
from lifestream.db import EntryStore

entry_store = EntryStore()

logger = logging.getLogger("Instagram")


lifestream.arguments.add_argument(
    "--all", required=False, help="Get all items", default=False, action="store_true"
)

args = lifestream.parse_args()

api = InstagramAPI(
    lifestream.config.get("instagram", "username"),
    lifestream.config.get("instagram", "password"),
)


def _item_image(item):
    if "image_versions2" in item:
        return item["image_versions2"]["candidates"][0]["url"]
    if "carousel_media" in item:
        return item["carousel_media"][0]["image_versions2"]["candidates"][0]["url"]
    raise Exception("No image thumbnail found")


def process_item(item):
    try:
        caption = item["caption"]["text"]
    except TypeError:
        caption = ""

    try:
        timestamp = datetime.fromtimestamp(item["taken_at"])
        url = "https://instagram.com/p/{}".format(item["code"])
        image = _item_image(item)
        logger.info("{}: {}".format(timestamp, caption.encode("ascii", "ignore")))
        entry_store.add_entry(
            "photo",
            item["id"],
            caption,
            "instagram",
            timestamp,
            url=url,
            image=image,
            fulldata_json=item,
        )
    except Exception as e:
        pprint(item)
        raise e


def process_feed():
    if args.all:
        feed = api.getTotalSelfUserFeed()
    else:
        feed = api.getSelfUserFeed()

    if not feed:
        logger.error("Failed to get feed")
        sys.exit(5)

    if feed is True:
        feed = api.LastJson["items"]

    for item in feed:
        process_item(item)


if api.login():
    process_feed()
else:
    logger.error("Can't login!")
