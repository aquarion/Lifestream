# -*- coding: utf-8 -*-
## 

#!/usr/bin/python
# Python
import dateutil.parser
import pytz
import sys
import os
import re
from datetime import datetime
import calendar
import rfc822
from urllib2 import URLError
import socket
import logging
import pickle
from pprint import pprint
import urlparse
from datetime import timedelta
import sys
import codecs

# Libraries
import facebook
import requests

# Local
import lifestream

Lifestream = lifestream.Lifestream()


UTF8Writer = codecs.getwriter('utf8')
sys.stdout = UTF8Writer(sys.stdout)

logger = logging.getLogger('Facebook')

lifestream.arguments.add_argument(
    '--reauth',
    required=False,
    help="Get new token",
    default=False,
    action='store_true')



args = lifestream.arguments.parse_args()


socket.setdefaulttimeout(60)  # Force a timeout if twitter doesn't respond


OAUTH_FILENAME = "%s/facebook.oauth" % (
    lifestream.config.get("global", "secrets_dir"))
APP_KEY = lifestream.config.get("facebook", "appid")
APP_SECRET = lifestream.config.get("facebook", "secret")

def authenticate(OAUTH_FILENAME, appid, secret, force_reauth=False):
    request_token_url = 'https://www.facebook.com/dialog/oauth?client_id=%s&redirect_uri=http://www.nicholasavenell.com/facebook/catch.php&response_type=token&scope=user_posts,user_status' % appid
    access_token_url = 'http://www.tumblr.com/oauth/access_token'
    authorize_url = 'http://www.tumblr.com/oauth/authorize'

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
        print "Go to the following link in your browser:"
        print request_token_url
        print

        accepted = 'n'
        while accepted.lower() == 'n':
            accepted = raw_input('Have you authorized me? (y/n) ')
        access_key = raw_input('What is the access code? ')

        logger.debug(access_key)
        print "Access key:", access_key

        extend_token_url = "https://graph.facebook.com/oauth/access_token?grant_type=fb_exchange_token&client_id=%s&client_secret=%s&fb_exchange_token=%s" % (appid, secret, access_key)
        extend_token = requests.get(extend_token_url)
        oauth_token = urlparse.parse_qs(extend_token.text)

        delta = timedelta(seconds=int(oauth_token['expires'][0]))
        oauth_token['expire_dt'] = datetime.now() + delta;
            
        f = open(OAUTH_FILENAME, "w")
        pickle.dump(oauth_token, f)
        f.close()

    return oauth_token


def some_action(post, graph, profile):

    visible_filters = ['LARP', "Unwork"]

    filters = {
        '15295050107' : "LARP",
        '10152343976945108' : "Unwork",
    '10151965973020108' : "LimitList"
    }

    if 'application' in post and 'namespace' in post['application'] and post['application']['namespace'] == "twitter":
        return

    if post['privacy']['value'] == "SELF":
        return

    #pprint(post)

    show = True

    url = "https://www.facebook.com/%s/posts/%s" % (profile['id'], post['id'].split("_")[1])

    if post['privacy']['value'] == "CUSTOM":
        if not post['privacy']['allow']:
            logger.info("Ignoring post %s due to an ad-hoc privacy filter" % url)
        elif post['privacy']['allow'] in filters:
            filter_name = filters[post['privacy']['allow']]
            # print "... That's the %s filter" % filter_name
            if filter_name in visible_filters:
                # print "... Keep that"
                show = True
            else:
                # print "... hide that"
                show = False
        else:
            logger.error("[ERROR] on %s - List ID %s not known" % (url, post['privacy']['allow'] ))
            show = False


    if not show:
        return
        
    if 'picture' in post:
        image = post['picture']
    else:
        image = False


    if not 'message' in post:
        post['message'] = '';

    # Lifestream.add_entry(
    #     post['type'],
    #     post['id'],
    #     post['message'],
    #     "facebook",
    #     post['created_time'],
    #     url=url,
    #     fulldata_json=o_item)
    # Lifestream.add_entry(
    #         post['type'],
    #         post['id'],
    #         post['message'],
    #         "facebook",
    #         post['created_time'],
    #         url=url,
    #         image=image,
    #         fulldata_json=post)

    print "SYSX", post['created_time'], url
    print post['message']
    print "SYSX---------------------------------------------------------------------------------------------------------------- NEW ENTRY"

credentials = authenticate(OAUTH_FILENAME, APP_KEY, APP_SECRET, args.reauth)


if datetime.now() > credentials['expire_dt']:
    logger.error("Token has expired! {} days!".format(delta.days))
    print "Token has expired!"

delta = credentials['expire_dt'] - datetime.now()

if delta.days <= 7:
    logger.warning("Token will expire in {} days!".format(delta.days))
    print "Token will expire in {} days!".format(delta.days)
else:
    logger.info("Token will expire in {} days!".format(delta.days))

graph = facebook.GraphAPI(credentials['access_token'][0])
profile = graph.get_object('me')
posts = graph.get_object("idlespeculation/posts", fields="application,message,type,privacy,status_type,source,properties,link,picture,created_time")

# Wrap this block in a while loop so we can keep paginating requests until
# finished.
page = 0
while True:
    page += 1
    sys.stderr.write('Page %s \n' % page)
    [some_action(post=post,graph=graph,profile=profile) for post in posts['data']]
    # if page >= 5:
    #     #break
    #     pass
    try:
        # Perform some action on each post in the collection we receive from
        # Facebook.
        # Attempt to make a request to the next page of data, if it exists.
        posts = requests.get(posts['paging']['next']).json()
        #raise KeyError;
    except KeyError:
        # When there are no more pages (['paging']['next']), break from the
        # loop and end the script.
        sys.stderr.write("No next")
        break