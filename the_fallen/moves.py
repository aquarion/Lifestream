##

#!/usr/bin/python
# Python
import logging
import pickle
import socket
import sys
from datetime import datetime, timedelta

import CodeFetcher9000
import pytz

# Libraries
import requests

# Local
import lifestream

Lifestream = lifestream.Lifestream()

logger = logging.getLogger("Moves")

lifestream.arguments.add_argument(
    "--reauth", required=False, help="Get new token", default=False, action="store_true"
)

lifestream.arguments.add_argument(
    "--import-all",
    required=False,
    help="Import all data",
    default=False,
    action="store_true",
)


args = lifestream.arguments.parse_args()


socket.setdefaulttimeout(60)  # Force a timeout if twitter doesn't respond


OAUTH_FILENAME = "%s/moves.oauth" % (
    lifestream.config.get("global", "secrets_dir"))
APP_KEY = lifestream.config.get("moves", "key")
APP_SECRET = lifestream.config.get("moves", "secret")

FoursquareAPI = lifestream.FoursquareAPI(Lifestream)

# authenticate(OAUTH_FILENAME, appid, secret, force_reauth=False):


def authenticate(OAUTH_FILENAME, appid, secret, force_reauth=False):

    scope = "activity+location"
    request_token_url = (
        "https://api.moves-app.com/oauth/v1/authorize?response_type=code&client_id=%s&scope=%s"
        % (appid, scope)
    )

    if not force_reauth:
        try:
            f = open(OAUTH_FILENAME, "rb")
            oauth_token = pickle.load(f)
            f.close()
        except:
            logger.error("Couldn't open %s, reloading..." % OAUTH_FILENAME)
            oauth_token = False
    else:
        oauth_token = False

    try:
        CodeFetcher9000.are_we_working()
        CodeFetcher9000.get_url()
        UseCodeFetcher = True
    except CodeFetcher9000.WeSayNotToday:
        try:
            "{}/keyback/wow.py".format(lifestream.config.get("dayze", "base")),
            UseCodeFetcher = False
        except ConfigParser.Error:
            logger.error("Dayze base not configured")
            print(
                "To catch an OAuth request, you need either CodeFetcher9000 or Dayze configured in config.ini"
            )
            sys.exit(32)

    if oauth_token:

        expiration_date = oauth_token["expire_dt"]
        if datetime.now() > expiration_date:
            print("Token has expired!")

        delta = expiration_date - datetime.now()

        if delta.days <= 7:
            print("Token will expire in {} days!".format(delta.days))

        return oauth_token

    # Step 2: Redirect to the provider. Since this is a CLI script we do not
    # redirect. In a web application you would redirect the user to the URL
    # below.

    print("Go to the following link in your browser:")
    print(request_token_url)
    print()

    if UseCodeFetcher:
        oauth_redirect = CodeFetcher9000.get_code("code")
        access_key = oauth_redirect["code"][0]
    else:
        print("If you configure CodeFetcher9000, this is a lot easier.")
        print(" - ")
        access_key = input("What is the PIN? ")

    extend_token_url = (
        "https://api.moves-app.com/oauth/v1/access_token?grant_type=authorization_code&code=%s&client_id=%s&client_secret=%s"
        % (access_key, appid, secret)
    )
    extend_token = requests.post(extend_token_url)
    oauth_token = extend_token.json()

    delta = timedelta(seconds=int(oauth_token["expires_in"]))
    oauth_token["expire_dt"] = datetime.now() + delta

    f = open(OAUTH_FILENAME, "w")
    pickle.dump(oauth_token, f)
    f.close()

    return oauth_token


credentials = authenticate(OAUTH_FILENAME, APP_KEY, APP_SECRET, args.reauth)


if datetime.now() > credentials["expire_dt"]:
    logger.error("Token has expired!")

delta = credentials["expire_dt"] - datetime.now()

if delta.days <= 7:
    logger.warning("Token will expire in {} days!".format(delta.days))
else:
    logger.info("Token will expire in {} days!".format(delta.days))


def dt_parse(t):
    ret = datetime.strptime(t[0:15], "%Y%m%dT%H%M%S")

    if t[15] == "+":
        ret -= timedelta(hours=int(t[16:18]), minutes=int(t[18:]))
    elif t[15] == "-":
        ret += timedelta(hours=int(t[16:18]), minutes=int(t[18:]))
    elif t[15] == "Z":
        pass
    else:
        raise Exception("Bad time format %s, %s" % (t, t[15]))
    return ret.replace(tzinfo=pytz.UTC)


def process_day(day):
    events_count = 0
    logger.info("----" + day["date"])
    if day["segments"]:
        for segment in day["segments"]:
            start = dt_parse(segment["startTime"])
            events_count += 1
            if "place" in segment:
                place = segment["place"]
                name = False
                if "name" in place:
                    logger.info("Moves: %s" % place["name"])
                    name = place["name"]
                else:
                    try:
                        fsq = FoursquareAPI.search_near(
                            place["location"]["lat"], place["location"]["lon"]
                        )
                        # ipdb.set_trace()
                        if "venues" not in fsq["response"]:
                            if "checkins" in fsq["response"]:
                                logger.info("Problem with Foursquare")
                                raise Exception("Trouble with Foursquare")
                            else:
                                logger.info("Serious Problem with Foursquare")
                                raise Exception("Trouble with Foursquare")
                        top_match = fsq["response"]["venues"][0]
                        if (
                            "count" in top_match["beenHere"]
                            and top_match["beenHere"]["count"] > 0
                        ):
                            logger.info("Fsq:  %s" % top_match["name"])
                            name = top_match["name"]
                        else:
                            raise Exception("Not found")
                    except:
                        logger.info(
                            "Moves: %s %s  (Nope)"
                            % (place["location"]["lat"], place["location"]["lon"])
                        )

                Lifestream.add_location(
                    start,
                    "Moves",
                    place["location"]["lat"],
                    place["location"]["lon"],
                    name,
                )
    if day["summary"]:
        for activity in day["summary"]:
            logger.info(
                "Activity: %sm %s" % (
                    activity["distance"], activity["activity"])
            )
    return events_count


payload = {
    "access_token": credentials["access_token"],
    "pastDays": 7,
    "trackPoints": "true",
}

BASEURL = "https://api.moves-app.com/api/1.1"

if args.import_all:
    logger.info("Import All")
    no_data_weeks = 0
    now = datetime.now()
    now = datetime(2017, 1, 8)
    a_week = timedelta(days=7)
    while no_data_weeks < 3:
        week = now.isocalendar()[1]
        url = "%s/user/storyline/daily/%s-W%s" % (BASEURL, now.year, week)
        profile = requests.get(url, params=payload).json()
        events_count = 0
        for day in profile:
            if "date" in day:
                events = process_day(day)
                events_count += events

        now = now - a_week
        if events_count == 0:
            logger.info("Nothing this week")
            no_data_weeks += 1
        else:
            no_data_weeks = 0

else:

    url = BASEURL + "/user/storyline/daily"

    profile = requests.get(url, params=payload).json()

    for day in profile:
        process_day(day)
        # datetime(year, month, day[, hour[, minute[, second[,
        # microsecond[,tzinfo]]]]])
