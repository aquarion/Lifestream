#!/usr/bin/python
# Python
import logging
import re
import socket
import sys
from urllib.error import URLError

import dateutil.parser

# Local
import lifestream
import pytz

# Libraries
import twitter
from lifestream.oauth_utils import read_token_file

Lifestream = lifestream.Lifestream()


lifestream.arguments.add_argument(
    "--catchup",
    required=False,
    help="Get all tweets",
    default=False,
    action="store_true",
)

lifestream.arguments.add_argument(
    "--reauth", required=False, help="Get new token", default=False, action="store_true"
)

logger = logging.getLogger("Twitter")
args = lifestream.arguments.parse_args()


socket.setdefaulttimeout(60)  # Force a timeout if twitter doesn't respond


OAUTH_FILENAME = "%s/twitter.oauth" % (lifestream.config.get("global", "secrets_dir"))
CONSUMER_KEY = lifestream.config.get("twitter", "consumer_key")
CONSUMER_SECRET = lifestream.config.get("twitter", "consumer_secret")


ACCOUNTS = lifestream.config.get("twitter", "accounts")

if not ACCOUNTS:
    logger.error("No twitter accounts found in config")
    sys.exit(5)

oauth_token, oauth_token_secret = read_token_file(OAUTH_FILENAME)

api = twitter.Api(
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    access_token_key=oauth_token,
    access_token_secret=oauth_token_secret,
    tweet_mode="extended",
)


def process_tweet(account, status):

    id = status.id_str
    image = status.user.profile_image_url_https
    message = status.full_text
    source = status.source
    logger.debug(" -  %s" % status.full_text)

    source = re.sub(r"<[^>]*?>", "", source)

    url = "http://twitter.com/%s/status/%s" % (account, id)

    localdate = dateutil.parser.parse(status.created_at)
    utcdate = localdate.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")

    Lifestream.add_entry(
        "twitter",
        id,
        message,
        source,
        utcdate,
        url=url,
        image=image,
        fulldata_json=status.AsDict(),
    )


for account in ACCOUNTS.split(","):
    logger.debug("Loading tweets for %s" % account)
    try:
        timeline = api.GetUserTimeline(screen_name=account)
        earliest_tweet = min(timeline, key=lambda x: x.id).id

    except ValueError:
        sys.exit(4)
    except URLError as e:
        if not e.reason[0] == 104:
            logger.error("Caught error %s" % e.reason[0])
            logger.error(e.reason)
        sys.exit(5)
    # except Exception as e:
    #     logger.error("Caught error %s" % Exception)
    #     logger.error(e)
    #     sys.exit(12)
    # logger.info('-- Welcome to Twipistula')

    for status in timeline:
        process_tweet(account, status)

    while args.catchup:
        tweets = api.GetUserTimeline(
            screen_name=account, max_id=earliest_tweet, count=200
        )
        new_earliest = min(tweets, key=lambda x: x.id).id

        if not tweets or new_earliest == earliest_tweet:
            break
        else:
            earliest_tweet = new_earliest
            logger.debug("getting tweets before: %s" % earliest_tweet)
            for status in tweets:
                process_tweet(account, status)
