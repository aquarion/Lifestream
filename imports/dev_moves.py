
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

# Libraries
import facebook
import requests

# Local
import lifestream

from pprint import pprint

Lifestream = lifestream.Lifestream()

logger = logging.getLogger('Moves')

lifestream.arguments.add_argument(
    '--reauth',
    required=False,
    help="Get new token",
    default=False,
    action='store_true')



args = lifestream.arguments.parse_args()


socket.setdefaulttimeout(60)  # Force a timeout if twitter doesn't respond


OAUTH_FILENAME = "%s/moves.oauth" % (
    lifestream.config.get("global", "secrets_dir"))
APP_KEY = lifestream.config.get("moves", "key")
APP_SECRET = lifestream.config.get("moves", "secret")

def authenticate(OAUTH_FILENAME, appid, secret, force_reauth=False):
    scope = "activity+location"
    request_token_url = 'https://api.moves-app.com/oauth/v1/authorize?response_type=code&client_id=%s&scope=%s' % (appid, scope)

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

	extend_token_url = "https://api.moves-app.com/oauth/v1/access_token?grant_type=authorization_code&code=%s&client_id=%s&client_secret=%s" % (access_key, appid, secret)
	extend_token = requests.post(extend_token_url)
	oauth_token = extend_token.json()

	delta = timedelta(seconds=int(oauth_token['expires_in']))
	oauth_token['expire_dt'] = datetime.now() + delta;
        
	f = open(OAUTH_FILENAME, "w")
        pickle.dump(oauth_token, f)
        f.close()

    return oauth_token


credentials = authenticate(OAUTH_FILENAME, APP_KEY, APP_SECRET, args.reauth)


if datetime.now() > credentials['expire_dt']:
	logger.error("Token has expired!")

delta = credentials['expire_dt'] - datetime.now()

if delta.days <= 7:
	logger.warning("Token will expire in {} days!".format(delta.days))
else:
    logger.info("Token will expire in {} days!".format(delta.days))


payload = { 
	'access_token' : credentials['access_token'],
	'pastDays'     : 7,
	'trackPoints'  : "true"
	}

BASEURL = "https://api.moves-app.com/api/1.1"

url = BASEURL + "/user/storyline/daily"

profile = requests.get(url, params=payload);

pprint(profile.json())

