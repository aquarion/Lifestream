#!/usr/bin/python

import lifestream

from pprint import pprint

import sys
import urlparse
import cPickle as pickle
import simplejson
import datetime
import dateutil.parser
from time import mktime


from pytumblr import TumblrRestClient
import oauth2 as oauth

import ipdb

Lifestream = lifestream.Lifestream()

OAUTH_TUMBLR = lifestream.config.get("tumblr", "secrets_file")


def tumblrAuth(config, OAUTH_TUMBLR):
    consumer_key = config.get("tumblr", "consumer_key")
    consumer_secret = config.get("tumblr", "secret_key")

    request_token_url = 'http://www.tumblr.com/oauth/request_token'
    access_token_url = 'http://www.tumblr.com/oauth/access_token'
    authorize_url = 'http://www.tumblr.com/oauth/authorize'

    try:
        f = open(OAUTH_TUMBLR, "rb")
        oauth_token = pickle.load(f)
        f.close()
    except:
        print "Couldn't open %s, reloading..." % OAUTH_TUMBLR
        oauth_token = False

    if(not oauth_token):
        consumer = oauth.Consumer(consumer_key, consumer_secret)
        client = oauth.Client(consumer)
        resp, content = client.request(request_token_url, "GET")
        if resp['status'] != '200':
            raise Exception("Invalid response %s." % resp['status'])

        request_token = dict(urlparse.parse_qsl(content))
        print "Go to the following link in your browser:"
        print "%s?oauth_token=%s" % (authorize_url, request_token['oauth_token'])
        print

        accepted = 'n'
        while accepted.lower() == 'n':
            accepted = raw_input('Have you authorized me? (y/n) ')
        oauth_verifier = raw_input('What is the PIN? ')

        token = oauth.Token(
            request_token['oauth_token'],
            request_token['oauth_token_secret'])
        token.set_verifier(oauth_verifier)
        client = oauth.Client(consumer, token)

        resp, content = client.request(access_token_url, "POST")
        oauth_token = dict(urlparse.parse_qsl(content))
        print resp

        print oauth_token
        print "Access key:", oauth_token['oauth_token']
        print "Access Secret:", oauth_token['oauth_token_secret']

        f = open(OAUTH_TUMBLR, "w")
        pickle.dump(oauth_token, f)
        f.close()

    return TumblrRestClient(
        consumer_key,
        consumer_secret,
        oauth_token['oauth_token'],
        oauth_token['oauth_token_secret'])


def cursor(dbcxn):
    dbc = dbcxn.cursor()
    dbc.execute('SET NAMES utf8;')
    dbc.execute('SET CHARACTER SET utf8;')
    dbc.execute('SET character_set_connection=utf8;')

    return dbc

to_blog = "aquarions-of-history"

dbcxn = lifestream.getDatabaseConnection()
cursor = cursor(dbcxn)

sql = "select title, date_created,url,fulldata_json, systemid from lifestream where source = 'tumblr' and date_created between %s and %s"

now = datetime.datetime.utcnow()

four_years = datetime.timedelta(days=365 * 4)
an_hour = datetime.timedelta(minutes=60)

datefrom = now - four_years
dateto = now - four_years + an_hour

tumblr = tumblrAuth(lifestream.config, OAUTH_TUMBLR)

cursor.execute(sql, (datefrom.isoformat(), dateto.isoformat()))
for post in cursor:
    systemid = post[4]
    print post[0]
    data = simplejson.loads(post[3])
    date_created = post[1]
    print date_created
    print date_created + four_years
    print '---'

    tumblr.reblog(
        "aquarions-of-history",
        id=systemid,
        reblog_key=data['reblog_key'],
    )