#!/usr/bin/python

import netflix

import lifestream

USER_ID = lifestream.config.get("netflix", "user_id")
API_KEY = lifestream.config.get("netflix", "api_key")
API_SECRET = lifestream.config.get("netflix", "api_secret")
OAUTH_TOKEN = lifestream.config.get("netflix", "oauth_token")
OAUTH_TOKEN_SECRET = lifestream.config.get("netflix", "oauth_token_secret")


n = netflix.NetflixAPI(api_key=API_KEY,
                       api_secret=API_SECRET,
                       oauth_token=OAUTH_TOKEN,
                       oauth_token_secret=OAUTH_TOKEN_SECRET
                       )

watched = n.get('users/%s/rental_history/watched' % USER_ID)
print watched

##
# This doesn't work for me, because Netflix's API doesn't do history for UK users, apparently.
# Maybe one day.
##
# NA 2012-04-14
