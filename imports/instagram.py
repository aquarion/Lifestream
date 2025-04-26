#!/usr/bin/python
# -*- coding: utf-8 -*-

import codecs
import configparser  # For the exceptions
import hashlib
import logging
# Python
import pickle
import socket
import sys
from datetime import datetime
from pprint import pprint

import pytz
from InstagramAPI import InstagramAPI

import CodeFetcher9000
# Local
import lifestream

Lifestream = lifestream.Lifestream()

logger = logging.getLogger("Instagram")


lifestream.arguments.add_argument(
    "--all", required=False, help="Get all items", default=False, action="store_true"
)

args = lifestream.arguments.parse_args()

api = InstagramAPI(
    lifestream.config.get("instagram", "username"),
    lifestream.config.get("instagram", "password"),
)
if api.login():
    if args.all:
        feed = api.getTotalSelfUserFeed()  # get self user feed
    else:
        feed = api.getSelfUserFeed()  # get self user feed

    if not feed:
        logger.error("Failed to get feed")
        sys.exit(5)

    if feed == True:
        feed = api.LastJson["items"]

    for item in feed:

        try:
            caption = item["caption"]["text"]
        except TypeError:
            caption = ""

        try:
            timestamp = datetime.fromtimestamp(item["taken_at"])
            url = "https://instagram.com/p/{}".format(item["code"])
            if "image_versions2" in item:
                image = item["image_versions2"]["candidates"][0]["url"]
            elif "carousel_media" in item:
                image = item["carousel_media"][0]["image_versions2"]["candidates"][0][
                    "url"
                ]
            else:
                raise Exception("No image thumbnail found")

            logger.info("{}: {}".format(timestamp, caption.encode("ascii", "ignore")))

            Lifestream.add_entry(
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
else:
    logger.error("Can't login!")
