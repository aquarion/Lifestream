#!/usr/bin/python

# Python
import logging
import os
import re
import sys
from datetime import datetime, timezone

# Local
import lifestream
import requests

# Libraries
from lifestream.oauth_utils import read_token_file

type = "location"
username = lifestream.config.get("foursquare", "username")
url = "http://foursquare.com/%s" % username


logger = logging.getLogger("Foursquare")
args = lifestream.arguments.parse_args()

# DB Setup

dbcxn = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)


# Oauth Setup

OAUTH_FILENAME = lifestream.config.get("foursquare", "secrets_file")
CONSUMER_KEY = lifestream.config.get("foursquare", "client_id")
CONSUMER_SECRET = lifestream.config.get("foursquare", "secret")

if not os.path.exists(OAUTH_FILENAME):
    logger.error("No OAUTH found at %s" % OAUTH_FILENAME)
    print("You need to run foursquare_oauth.py to generate the oauth key")
    sys.exit(5)

oauth_token, oauth_token_secret = read_token_file(OAUTH_FILENAME)


# Loop setup

Lifestream = lifestream.Lifestream()

URL_BASE = "https://api.foursquare.com/v2/%s"
# Get the data

payload = {"v": "20180226", "oauth_token": oauth_token}

r = requests.get(URL_BASE % "users/self/checkins", params=payload)

try:
    data = r.json()
except Exception:
    print(URL_BASE, "users/self/checkins", payload)
    print(r.text)
    sys.exit(5)

checkins = data["response"]["checkins"]["items"]

if "checkins" in list(data["response"].keys()):
    for location in checkins:
        source = "Foursquare"
        if "isMayor" in list(location.keys()) and location["isMayor"]:
            source = "Foursquare-Mayor"

        image = ""

        source = re.sub(r"<[^>]*?>", "", source)

        if "venue" in list(location.keys()):
            message = location["venue"]["name"]
            if len(location["venue"]["categories"]):
                for category in location["venue"]["categories"]:
                    if "primary" in list(category.keys()):
                        image = category["icon"]
                        image = image["prefix"] + "64.png"
        else:
            message = location["location"]["name"]

        epoch = location["createdAt"]
        # utctime = datetime.utcfromtimestamp(epoch)
        utctime = datetime.fromtimestamp(epoch, tz=timezone.utc)
        utcdate = utctime.strftime("%Y-%m-%d %H:%M")

        id = location["id"]

        url = "http://www.foursquare.com/%s/checkin/%s" % (username, id)

        # cursor.execute(s_sql, (type, id, message, utcdate, url, source, image))
        Lifestream.add_entry(
            type,
            id,
            message,
            source,
            utcdate,
            url=url,
            image=image,
            fulldata_json=location,
        )

        coordinates = location["venue"]["location"]

        logger.info("Checkin %s@%s" % (utcdate, location["venue"]["name"]))

        Lifestream.add_location(
            utctime,
            "foursquare",
            coordinates["lat"],
            coordinates["lng"],
            message,
            image,
        )
