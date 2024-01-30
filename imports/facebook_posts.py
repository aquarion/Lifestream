#!/usr/bin/python


# Python
import sys
from datetime import datetime
import socket
import logging
import pickle
from datetime import timedelta
import configparser  # For the exceptions
from pprint import pprint

import pymysql

# Libraries
import facebook
import requests

# Local
import lifestream
import CodeFetcher9000

from dateutil import parser as dtparser

Lifestream = lifestream.Lifestream()

logger = logging.getLogger('Facebook')

lifestream.arguments.add_argument(
    '--reauth',
    required=False,
    help="Get new token",
    default=False,
    action='store_true')

lifestream.arguments.add_argument(
    '--pages',
    required=False,
    type=int,
    help="Number of pages to go back. 0 (or --all) to go forever",
    default=5)

lifestream.arguments.add_argument(
    '--all',
    required=False,
    help="Get all posts",
    default=False,
    action='store_true')


args = lifestream.arguments.parse_args()


socket.setdefaulttimeout(60)  # Force a timeout if facebook doesn't respond


OAUTH_FILENAME = "%s/facebook.oauth" % (
    lifestream.config.get("global", "secrets_dir"))
APP_KEY = lifestream.config.get("facebook", "appid")
APP_SECRET = lifestream.config.get("facebook", "secret")


def authenticate(OAUTH_FILENAME, appid, secret, force_reauth=False):

    try:
        CodeFetcher9000.are_we_working()
        redirect_uri = CodeFetcher9000.get_url()
        UseCodeFetcher = True
    except CodeFetcher9000.WeSayNotToday:
        try:
            redirect_uri = '{}/facebook/catch.php'.format(
                lifestream.config.get(
                    "dayze",
                    "base")),
            UseCodeFetcher = False
        except configparser.Error:
            logger.error("Dayze base not configured")
            print(
                "To catch an OAuth request, you need either CodeFetcher9000 or Dayze configured in config.ini")
            sys.exit(32)

    request_token_url = 'https://www.facebook.com/dialog/oauth?client_id=%s&redirect_uri=%s&response_type=token&scope=user_posts' % (
        appid, redirect_uri)

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

    if(not oauth_token):
        print("Go to the following link in your browser:")
        print(request_token_url)
        print()

        if UseCodeFetcher:
            oauth_redirect = CodeFetcher9000.get_code("access_token")
            access_key = oauth_redirect['access_token'][0]
        else:
            print("If you configure CodeFetcher9000, this is a lot easier.")
            print(" - ")
            access_key = input('What is the PIN? ')

        extend_token_url = "https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s" % (
            appid, secret, access_key)
        extend_token = requests.get(extend_token_url)

        oauth_token = extend_token.json()

        print(oauth_token)

        delta = timedelta(seconds=int(oauth_token['expires_in']))
        oauth_token['expire_dt'] = datetime.now() + delta

        f = open(OAUTH_FILENAME, "wb")
        pickle.dump(oauth_token, f)
        f.close()

    return oauth_token


def some_action(post, graph, profile):

    visible_filters = lifestream.config.get("facebook", "visible_filters")

    filters = {}
    for key, value in lifestream.config.items("facebook:filters"):
        filters[key] = value

    if 'application' in post and 'namespace' in post[
            'application'] and post['application']['namespace'] == "twitter":
        return

    if post['privacy']['value'] == "SELF":
        return

    if 'picture' in post:
        image = post['picture']
    else:
        image = False

    if not 'message' in post:
        post['message'] = ''

    show = True

    url = "https://www.facebook.com/%s/posts/%s" % (
        profile['id'], post['id'].split("_")[1])

    post_filter_ids = set(post['privacy']['allow'].split(","))
    filter_ids = set(filters.keys())

    # '2020-03-17T10:27:08+0000
    dt = dtparser.parse(post['created_time'])

    logger.info("New Post: %s " % post['message'][0:60])

    if post['privacy']['value'] == "CUSTOM":
        if not post['privacy']['allow']:
            logger.info(
                "Ignoring post %s due to an ad-hoc privacy filter" %
                url)
        elif len(filter_ids.intersection(post_filter_ids)):
            for filter_id in list(post_filter_ids):
                if filter_id not in filters:
                    logger.info("... Filter ID %s unidentified" % filter_id)

                elif filters[filter_id] in visible_filters:
                    logger.info(
                        "... [%s] filter post, vote KEEP" % filters[filter_id])
                    # show = True
                    pass
                else:
                    logger.info(
                        "... [%s] filter post, vote HIDE" % filters[filter_id])
                    show = False
        else:
            logger.error(
                "[ERROR] on %s - List ID %s not known" %
                (url, post['privacy']['allow']))
            show = False
    else:
        logger.info('... %s privacy post, vote KEEP' %
                    post['privacy']['value'])

    if show:
        logger.info("... KEEP carries")
    else:
        logger.info("... HIDE carries")
        return

    # Lifestream.add_entry(
    #     post['type'],
    #     post['id'],
    #     post['message'],
    #     "facebook",
    #     post['created_time'],
    #     url=url,
    #     fulldata_json=o_item)

    try:
        Lifestream.add_entry(
            post['type'],
            post['id'],
            post['message'],
            "facebook",
            dt,
            url=url,
            image=image,
            fulldata_json=post)
    except pymysql.err.InternalError as e:
        if e[0] == 1366:
            logger.info(e)
        else:
            logger.error(e)


credentials = authenticate(OAUTH_FILENAME, APP_KEY, APP_SECRET, args.reauth)

delta = credentials['expire_dt'] - datetime.now()

if datetime.now() > credentials['expire_dt']:
    logger.error("Token has expired! {} days!".format(delta.days))
    print("Token has expired!")


if delta.days <= 7:
    logger.warning("Token will expire in {} days!".format(delta.days))
    print("Token will expire in {} days!".format(delta.days))
else:
    logger.info("Token will expire in {} days!".format(delta.days))

graph = facebook.GraphAPI(credentials['access_token'], version="3.1")
profile = graph.get_object('me')
posts = graph.get_object(
    "me/posts",
    fields="application,message,type,privacy,status_type,source,properties,link,picture,created_time")

# Wrap this block in a while loop so we can keep paginating requests until
# finished.

if args.pages == 0 or args.all:
	INFINITE=True
else:
	INFINITE=False


page = 0
while True:
    page += 1
    # print "Page ", pagea
    logger.info("Page {}".format(page))
    [some_action(post=post, graph=graph, profile=profile)
        for post in posts['data']]

    logger.info("Page %d of %d" % (page, args.pages))
    if not INFINITE and page >= args.pages:
        logger.info("I've hit the page limit. Buhbye")
        break
    try:
        # Perform some action on each post in the collection we receive from
        # Facebook.
        # Attempt to make a request to the next page of data, if it exists.
        posts = requests.get(posts['paging']['next']).json()
        #raise KeyError;
    except KeyError:
        # When there are no more pages (['paging']['next']), break from the
        # loop and end the script.
        logger.info("No more pages. Buhbye")
        break
