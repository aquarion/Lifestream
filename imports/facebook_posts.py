
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

# Libraries
import facebook
import requests

# Local
import lifestream

Lifestream = lifestream.Lifestream()

logger = logging.getLogger('Facebook')
args = lifestream.arguments.parse_args()


socket.setdefaulttimeout(60)  # Force a timeout if twitter doesn't respond


OAUTH_FILENAME = "%s/facebook.oauth" % (
    lifestream.config.get("global", "secrets_dir"))
APP_KEY = lifestream.config.get("facebook", "appid")
APP_SECRET = lifestream.config.get("facebook", "secret")

def authenticate(OAUTH_FILENAME, appid, secret):
    request_token_url = 'https://www.facebook.com/dialog/oauth?client_id=%s&redirect_uri=http://www.nicholasavenell.com/facebook/catch.php&response_type=token&scope=user_posts,user_status' % appid
    access_token_url = 'http://www.tumblr.com/oauth/access_token'
    authorize_url = 'http://www.tumblr.com/oauth/authorize'

    try:
        f = open(OAUTH_FILENAME, "rb")
        oauth_token = pickle.load(f)
        f.close()
    except:
        logger.error("Couldn't open %s, reloading..." % OAUTH_FILENAME)
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

        oauth_token = {
        'access_key': access_key
        }

        f = open(OAUTH_FILENAME, "w")
        pickle.dump(oauth_token, f)
        f.close()

    return oauth_token


def some_action(post, graph, profile):

    visible_filters = ['LARP', ]

    filters = {
        '15295050107' : "LARP",
        '10152343976945108' : "Limit List"
    }

    if 'application' in post and post['application']['namespace'] == "twitter":
        return

    if post['privacy']['value'] == "SELF":
        return

    #pprint(post)

    show = True

    if post['privacy']['value'] == "CUSTOM":
        if post['privacy']['allow'] in filters:
            filter_name = filters[post['privacy']['allow']]
            # print "... That's the %s filter" % filter_name
            if filter_name in visible_filters:
                # print "... Keep that"
                show = True
            else:
                # print "... hide that"
                show = False
        else:
            logger.error("[ERROR] %s not known" % post['privacy']['allow'] )
            show = False


    if not show:
        return
        
    if 'picture' in post:
        image = post['picture']
    else:
        image = False

    url = "https://www.facebook.com/%s/posts/%s" % (profile['id'], post['id'].split("_")[1])


    print "------"

    # Lifestream.add_entry(
    #     post['type'],
    #     post['id'],
    #     post['message'],
    #     "facebook",
    #     post['created_time'],
    #     url=url,
    #     fulldata_json=o_item)
    Lifestream.add_entry(
            post['type'],
            post['id'],
            post['message'],
            "facebook",
            post['created_time'],
            url=url,
            image=image,
            fulldata_json=post)


credentials = authenticate(OAUTH_FILENAME, APP_KEY, APP_SECRET)

graph = facebook.GraphAPI(credentials['access_key'])
profile = graph.get_object('me')
posts = graph.get_object("me/posts", fields="application,message,type,privacy,status_type,source,properties,link,picture,created_time")

# import ipdb
# ipdb.set_trace();

# Wrap this block in a while loop so we can keep paginating requests until
# finished.
while True:
    try:
        # Perform some action on each post in the collection we receive from
        # Facebook.
        [some_action(post=post,graph=graph,profile=profile) for post in posts['data']]
        # Attempt to make a request to the next page of data, if it exists.
        posts = requests.get(posts['paging']['next']).json()
        #raise KeyError;
    except KeyError:
        # When there are no more pages (['paging']['next']), break from the
        # loop and end the script.
        print "No next"
        break