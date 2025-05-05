#!/usr/bin/python
# -*- coding: utf-8 -*-

import datetime
import logging
import pickle as pickle

# Python
import urllib.parse

# Local
import lifestream
import oauth2 as oauth
import simplejson
from dateutil.relativedelta import relativedelta

# Libraries
from pytumblr import TumblrRestClient

# Libraries


Lifestream = lifestream.Lifestream()

logger = logging.getLogger("Histumblr")
args = lifestream.arguments.parse_args()

OAUTH_TUMBLR = lifestream.config.get("tumblr", "secrets_file")


def tumblrAuth(config, OAUTH_TUMBLR):
    consumer_key = config.get("tumblr", "consumer_key")
    consumer_secret = config.get("tumblr", "secret_key")

    request_token_url = "http://www.tumblr.com/oauth/request_token"
    access_token_url = "http://www.tumblr.com/oauth/access_token"
    authorize_url = "http://www.tumblr.com/oauth/authorize"

    try:
        f = open(OAUTH_TUMBLR, "rb")
        oauth_token = pickle.load(f)
        f.close()
    except:
        logger.error("Couldn't open %s, reloading..." % OAUTH_TUMBLR)
        oauth_token = False

    if not oauth_token:
        consumer = oauth.Consumer(consumer_key, consumer_secret)
        client = oauth.Client(consumer)
        resp, content = client.request(request_token_url, "GET")
        if resp["status"] != "200":
            raise Exception("Invalid response %s." % resp["status"])

        request_token = dict(urllib.parse.parse_qsl(content))
        print("Go to the following link in your browser:")
        print("%s?oauth_token=%s" % (authorize_url, request_token["oauth_token"]))
        print()

        accepted = "n"
        while accepted.lower() == "n":
            accepted = input("Have you authorized me? (y/n) ")
        oauth_verifier = input("What is the PIN? ")

        token = oauth.Token(
            request_token["oauth_token"], request_token["oauth_token_secret"]
        )
        token.set_verifier(oauth_verifier)
        client = oauth.Client(consumer, token)

        resp, content = client.request(access_token_url, "POST")
        oauth_token = dict(urllib.parse.parse_qsl(content))

        logger.debug(resp)
        logger.debug(oauth_token)
        print("Access key:", oauth_token["oauth_token"])
        print("Access Secret:", oauth_token["oauth_token_secret"])

        f = open(OAUTH_TUMBLR, "w")
        pickle.dump(oauth_token, f)
        f.close()

    return TumblrRestClient(
        consumer_key,
        consumer_secret,
        oauth_token["oauth_token"],
        oauth_token["oauth_token_secret"],
    )


def cursor(dbcxn):
    dbc = dbcxn.cursor()
    dbc.execute("SET NAMES utf8;")
    dbc.execute("SET CHARACTER SET utf8;")
    dbc.execute("SET character_set_connection=utf8;")

    return dbc


to_blog = "aquarions-of-history"

dbcxn = lifestream.getDatabaseConnection()
cursor = cursor(dbcxn)

sql = "select title, date_created,url,fulldata_json, systemid, source, type from lifestream where source = 'tumblr' and date_created between %s and %s"

now = datetime.datetime.now(datetime.UTC)

a_day = datetime.timedelta(days=1)
four_years = relativedelta(years=4)
ten_years = relativedelta(years=10)
an_hour = datetime.timedelta(minutes=60)
quarter_hour = datetime.timedelta(minutes=15)

datefrom = now - ten_years
dateto = now - ten_years + quarter_hour

tumblr = tumblrAuth(lifestream.config, OAUTH_TUMBLR)

cursor.execute(sql, (datefrom.isoformat(), dateto.isoformat()))
for post in cursor:
    title = post[0]
    date_created = post[1]
    url = post[2]
    fulldata = post[3]
    systemid = post[4]
    source = post[5]
    contenttype = post[6]

    if not title:
        logger.info("Skipping, no content")
        continue

    title = title.replace("@", "💬")

    logger.info(title)

    if fulldata:
        data = simplejson.loads(fulldata)

    logger.info(date_created)
    logger.info(date_created + ten_years)
    logger.info("---")

    tresponse = tumblr.reblog(
        "aquarions-of-history",
        id=systemid,
        reblog_key=data["reblog_key"],
        state="queue",
        date=date_created + ten_years,
    )

dbcxn.close()
