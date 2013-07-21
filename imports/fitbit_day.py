#!/usr/bin/python

import lifestream, lifestreamutils

import sys, cPickle as pickle
import simplejson
from datetime import datetime, timedelta
from time import mktime

import oauth2 as oauth

import fitbit

dbcxn = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)

OAUTH_SECRETS  = lifestream.config.get("fitbit", "secrets_file")

s_sql = u'replace into lifestream (`type`, `systemid`, `title`, `url`, `date_created`, `source`, `image`) values (%s, %s, %s, %s, %s, "", "");'


def fitbitAuth(config, OAUTH_SECRETS):
	consumer_key    = config.get("fitbit", "consumer_key")
	consumer_secret = config.get("fitbit", "secret_key")

	request_token_url = 'http://api.fitbit.com/oauth/request_token'
	access_token_url = 'http://api.fitbit.com/oauth/access_token'
	authorize_url = 'http://www.fitbit.com/oauth/authorize'

	try:
		f = open(OAUTH_SECRETS, "rb")
		oauth_token = pickle.load(f)
		f.close();
	except:
		print "Couldn't open %s, reloading..." % OAUTH_SECRETS
		oauth_token = False

	if(not oauth_token):
		consumer = oauth.Consumer(consumer_key, consumer_secret)
		client   = oauth.Client(consumer)
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

		token = oauth.Token(request_token['oauth_token'], request_token['oauth_token_secret'])
		token.set_verifier(oauth_verifier)
		client = oauth.Client(consumer, token)


		resp, content = client.request(access_token_url, "POST")
		oauth_token = dict(urlparse.parse_qsl(content))
		print resp

		print oauth_token
		print "Access key:", oauth_token['oauth_token']
		print "Access Secret:", oauth_token['oauth_token_secret']

		f = open(OAUTH_SECRETS, "w")
		pickle.dump(oauth_token, f)
		f.close();
		
	return fitbit.Fitbit(consumer_key, consumer_secret, user_key=oauth_token['oauth_token'], user_secret=oauth_token['oauth_token_secret'])

fbcxn = fitbitAuth(lifestream.config, OAUTH_SECRETS)

s_sql = u'replace into lifestream (`type`, `systemid`, `title`, `url`, `date_created`, `source`, `image`, `fulldata_json`) values (%s, %s, %s, %s, %s, "fitbit", %s, %s);'


for sleep in fbcxn.sleep()['sleep']:

	type  = "sleep"
	id    = sleep['logId']
	url   = ''
	image = ''
	date  = sleep['startTime']


	sleep['minuteData'] = {}
	toSleep = lifestream.niceTimeDelta(sleep['minutesToFallAsleep'] * 60)
	asleep  = lifestream.niceTimeDelta(sleep['duration']/1000)

	title = "Took %s to fall asleep for %s (%d%% efficent sleep)." % (toSleep, asleep, sleep['efficiency'])

	cursor.execute(s_sql, (type, id, title, url, date, image, simplejson.dumps(sleep)))
	lifestreamutils.newstat(sleep['startTime'], "sleep", sleep['minutesAsleep'])

for badge in fbcxn.get_badges()['badges']:
	type  = "badge"
	id    = "%s%s" % (badge['badgeType'], badge['value'])
	url   = ''
	image = badge['image50px']
	date  = badge['dateTime']
	cursor.execute(s_sql, (type, id, "", url, date, image, simplejson.dumps(badge)))


for day in range(0,7):
	this_day = datetime.now() - timedelta(days=day)
	this_day_str = this_day.strftime("%Y-%m-%d");

	allsteps = fbcxn.time_series("activities/steps", period="1d", base_date=this_day_str)['activities-steps']
	for steps in allsteps:
		#print "Steps for %s : %s" % (steps['dateTime'], steps['value'])
		if steps['value'] > 0:
			cursor.execute(s_sql, ("steps", "steps"+steps['dateTime'], "%s steps" % steps['value'], "", steps['dateTime'], "", simplejson.dumps(steps)))
			lifestreamutils.newstat(steps['dateTime'], "steps", steps['value'])

	allscore = fbcxn.time_series("activities/activeScore", period="1d", base_date=this_day_str)['activities-activeScore']
	for score in allscore:
		#print "score for %s : %s" % (score['dateTime'], score['value'])
		if score['value'] > 0:
			cursor.execute(s_sql, ("activeScore", "activeScore"+score['dateTime'], "activeScore of %s" % score['value'], "", score['dateTime'], "", simplejson.dumps(score)))
			lifestreamutils.newstat(score['dateTime'], "activeScore", score['value'])