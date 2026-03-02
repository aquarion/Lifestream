#!/usr/bin/python

# Python
import logging
import os
import re
import sys
from datetime import datetime, timezone

import requests
from httplib2 import Http

# Local
import lifestream
from lifestream.db import EntryStore
from lifestream.db import get_connection, get_cursor
from lifestream.oauth_utils import read_token_file, write_token_file

type = "location"
username = lifestream.config.get("foursquare", "username")
url = "http://foursquare.com/%s" % username


logger = logging.getLogger("Foursquare")

lifestream.arguments.add_argument(
    "--reauth",
    required=False,
    help="Get new OAuth token",
    default=False,
    action="store_true",
)
lifestream.arguments.add_argument(
    "--auth-code",
    required=False,
    help="OAuth authorization code from browser redirect",
    default=None,
)

args = lifestream.parse_args()


# Oauth Setup

OAUTH_FILENAME = lifestream.config.get("foursquare", "secrets_file")
CLIENT_ID = lifestream.config.get("foursquare", "client_id")
CLIENT_SECRET = lifestream.config.get("foursquare", "secret")
CALLBACK_URL = "www.github.com/aquarion/lifestream"


def authenticate(force_reauth=False, auth_code=None):
    """Handle Foursquare OAuth2 authentication."""
    
    # If we have a valid token file and not forcing reauth, use it
    if not force_reauth and os.path.exists(OAUTH_FILENAME):
        oauth_token, _ = read_token_file(OAUTH_FILENAME)
        if oauth_token:
            return oauth_token
    
    # OAuth2 flow
    if not auth_code:
        # Step 1: Direct user to authorize
        auth_url = (
            "https://foursquare.com/oauth2/authenticate?"
            f"client_id={CLIENT_ID}&response_type=code&redirect_uri={CALLBACK_URL}"
        )
        print("Go to the following link in your browser:")
        print(auth_url)
        print()
        print(f"Then run: {sys.argv[0]} --auth-code [CODE_FROM_URL]")
        sys.exit(0)
    
    # Step 2: Exchange code for access token
    token_url = (
        f"https://foursquare.com/oauth2/access_token?"
        f"client_id={CLIENT_ID}&client_secret={CLIENT_SECRET}"
        f"&grant_type=authorization_code&redirect_uri={CALLBACK_URL}&code={auth_code}"
    )
    
    web = Http()
    resp, content = web.request(token_url)
    
    if resp.status != 200:
        print(f"Error getting access token: {resp.status}")
        print(content)
        sys.exit(5)
    
    import json
    token_data = json.loads(content)
    access_token = token_data.get("access_token")
    
    if not access_token:
        print("No access_token in response:")
        print(token_data)
        sys.exit(5)
    
    # Save token
    write_token_file(OAUTH_FILENAME, access_token, "")
    print(f"Token saved to {OAUTH_FILENAME}")
    
    return access_token


# Handle auth if needed
if args.reauth or args.auth_code or not os.path.exists(OAUTH_FILENAME):
    oauth_token = authenticate(force_reauth=args.reauth, auth_code=args.auth_code)
    if args.auth_code:
        print("Authentication successful! You can now run without --auth-code")
        sys.exit(0)
else:
    oauth_token, _ = read_token_file(OAUTH_FILENAME)


# DB Setup (after auth handling so --reauth doesn't need DB)

dbcxn = get_connection()
cursor = get_cursor(dbcxn)

# Loop setup

entry_store = EntryStore()

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
        entry_store.add_entry(
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

        entry_store.add_location(
            utctime,
            "foursquare",
            coordinates["lat"],
            coordinates["lng"],
            message,
            image,
        )
