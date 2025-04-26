#!/usr/bin/python

# Python
import logging
import pickle as pickle
import pprint
from datetime import datetime, timedelta

import fitbit
# Libraries
from fitbit.api import FitbitOauthClient

# Local
import lifestream
import lifestreamutils

Lifestream = lifestream.Lifestream()

OAUTH_SECRETS = lifestream.config.get("fitbit", "secrets_file")


logger = logging.getLogger("Fitbit Day")
args = lifestream.arguments.parse_args()


def fitbitAuth(config, OAUTH_SECRETS):
    CLIENT_KEY = config.get("fitbit", "consumer_key")
    CLIENT_SECRET = config.get("fitbit", "secret_key")

    request_token_url = "https://api.fitbit.com/oauth/request_token"
    access_token_url = "https://api.fitbit.com/oauth/access_token"
    authorize_url = "https://www.fitbit.com/oauth/authorize"

    try:
        f = open(OAUTH_SECRETS, "rb")
        token = pickle.load(f)
        f.close()
    except:
        logger.error("Couldn't open %s, reloading..." % OAUTH_SECRETS)
        token = False

    if not token:
        pp = pprint.PrettyPrinter(indent=4)
        client = FitbitOauthClient(CLIENT_KEY, CLIENT_SECRET)

        print("* Obtain a request token ...\n")
        token = client.fetch_request_token()
        print("RESPONSE")
        pp.pprint(token)
        print("")

        print("* Authorize the request token in your browser\n")

        print(client.authorize_token_url())

        try:
            verifier = input("Verifier: ")
        except NameError:
            # Python 3.x
            verifier = eval(input("Verifier: "))

        # get access token
        print("\n* Obtain an access token ...\n")
        token = client.fetch_access_token(verifier)
        print("RESPONSE")
        pp.pprint(token)
        print("")

        print(token)
        print("Access key:", token["oauth_token"])
        print("Access Secret:", token["oauth_token_secret"])

        f = open(OAUTH_SECRETS, "w")
        pickle.dump(token, f)
        f.close()

    return fitbit.Fitbit(
        CLIENT_KEY,
        CLIENT_SECRET,
        resource_owner_key=token["oauth_token"],
        resource_owner_secret=token["oauth_token_secret"],
    )


fbcxn = fitbitAuth(lifestream.config, OAUTH_SECRETS)

for sleep in fbcxn.sleep()["sleep"]:

    type = "sleep"
    id = sleep["logId"]
    url = ""
    image = ""
    date = sleep["startTime"]

    sleep["minuteData"] = {}
    toSleep = lifestream.niceTimeDelta(sleep["minutesToFallAsleep"] * 60)
    asleep = lifestream.niceTimeDelta(sleep["duration"] / 1000)

    title = "Took %s to fall asleep for %s (%d%% efficent sleep)." % (
        toSleep,
        asleep,
        sleep["efficiency"],
    )

    logger.info("Sleep: %s" % title)
    Lifestream.add_entry(
        type=type, id=id, title=title, source="fitbit", date=date, fulldata_json=sleep
    )
    lifestreamutils.newstat(sleep["startTime"], "sleep", sleep["minutesAsleep"])

for badge in fbcxn.get_badges()["badges"]:
    type = "badge"
    id = badge["badgeType"] + str(badge["value"]) + badge["dateTime"]
    url = ""
    image = badge["image75px"]
    date = badge["dateTime"]

    logger.info("Badge: %s" % badge["image75px"])
    Lifestream.add_entry(
        type=type, id=id, title="", source="fitbit", date=date, fulldata_json=badge
    )


for day in range(0, 7):
    this_day = datetime.now() - timedelta(days=day)
    this_day_str = this_day.strftime("%Y-%m-%d")

    allsteps = fbcxn.time_series(
        "activities/steps", period="1d", base_date=this_day_str
    )["activities-steps"]
    for steps in allsteps:
        # print "Steps for %s : %s" % (steps['dateTime'], steps['value'])
        if int(steps["value"]) > 0:
            logger.info("Steps: %s" % steps["value"])
            Lifestream.add_entry(
                type="steps",
                id="steps" + steps["dateTime"],
                title="%s steps" % steps["value"],
                source="fitbit",
                date=steps["dateTime"],
                fulldata_json=steps,
                update=True,
            )
            lifestreamutils.newstat(steps["dateTime"], "steps", steps["value"])

    allscore = fbcxn.time_series(
        "activities/activeScore", period="1d", base_date=this_day_str
    )["activities-activeScore"]
    for score in allscore:
        # print "score for %s : %s" % (score['dateTime'], score['value'])
        if int(score["value"]) > 0:
            logger.info("Score: %s" % score["value"])
            Lifestream.add_entry(
                type="activeScore",
                id="activeScore" + score["dateTime"],
                title="activeScore of %s" % score["value"],
                source="fitbit",
                date=score["dateTime"],
                fulldata_json=score,
                update=True,
            )
            lifestreamutils.newstat(score["dateTime"], "activeScore", score["value"])
