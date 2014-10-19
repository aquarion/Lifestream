#!/usr/bin/python

import lifestream
import lifestreamutils

import sys
import cPickle as pickle
from datetime import datetime, timedelta

import oauth2 as oauth


Lifestream = lifestream.Lifestream()

import fitbit

OAUTH_SECRETS = lifestream.config.get("fitbit", "secrets_file")


def fitbitAuth(config, OAUTH_SECRETS):
    consumer_key = config.get("fitbit", "consumer_key")
    consumer_secret = config.get("fitbit", "secret_key")

    request_token_url = 'https://api.fitbit.com/oauth/request_token'
    access_token_url = 'https://api.fitbit.com/oauth/access_token'
    authorize_url = 'https://www.fitbit.com/oauth/authorize'

    try:
        f = open(OAUTH_SECRETS, "rb")
        oauth_token = pickle.load(f)
        f.close()
    except:
        print "Couldn't open %s, reloading..." % OAUTH_SECRETS
        oauth_token = False

    if(not oauth_token):
        consumer = oauth.Consumer(consumer_key, consumer_secret)
        client = oauth.Client(consumer)
        resp, content = client.request(request_token_url, "GET")
	print request_token_url
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

        f = open(OAUTH_SECRETS, "w")
        pickle.dump(oauth_token, f)
        f.close()

    return fitbit.Fitbit(
        consumer_key,
        consumer_secret,
        user_key=oauth_token['oauth_token'],
        user_secret=oauth_token['oauth_token_secret'])

fbcxn = fitbitAuth(lifestream.config, OAUTH_SECRETS)

for sleep in fbcxn.sleep()['sleep']:

    type = "sleep"
    id = sleep['logId']
    url = ''
    image = ''
    date = sleep['startTime']

    sleep['minuteData'] = {}
    toSleep = lifestream.niceTimeDelta(sleep['minutesToFallAsleep'] * 60)
    asleep = lifestream.niceTimeDelta(sleep['duration'] / 1000)

    title = "Took %s to fall asleep for %s (%d%% efficent sleep)." % (
        toSleep, asleep, sleep['efficiency'])

    Lifestream.add_entry(
        type=type,
        id=id,
        title=title,
        source="fitbit",
        date=date,
        fulldata_json=sleep)
    lifestreamutils.newstat(
        sleep['startTime'],
        "sleep",
        sleep['minutesAsleep'])

for badge in fbcxn.get_badges()['badges']:
    type = "badge"
    id = badge['badgeType'] + str(badge['value']) + badge['dateTime']
    url = ''
    image = badge['image75px']
    date = badge['dateTime']

    Lifestream.add_entry(
        type=type,
        id=id,
        title='',
        source="fitbit",
        date=date,
        fulldata_json=badge)


for day in range(0, 7):
    this_day = datetime.now() - timedelta(days=day)
    this_day_str = this_day.strftime("%Y-%m-%d")

    allsteps = fbcxn.time_series(
        "activities/steps",
        period="1d",
        base_date=this_day_str)['activities-steps']
    for steps in allsteps:
        # print "Steps for %s : %s" % (steps['dateTime'], steps['value'])
        if int(steps['value']) > 0:
            Lifestream.add_entry(
                type="steps",
                id="steps" +
                steps['dateTime'],
                title="%s steps" %
                steps['value'],
                source="fitbit",
                date=steps['dateTime'],
                fulldata_json=steps,
                update=True)
            lifestreamutils.newstat(steps['dateTime'], "steps", steps['value'])

    allscore = fbcxn.time_series(
        "activities/activeScore",
        period="1d",
        base_date=this_day_str)['activities-activeScore']
    for score in allscore:
        # print "score for %s : %s" % (score['dateTime'], score['value'])
        if int(score['value']) > 0:
            Lifestream.add_entry(
                type="activeScore",
                id="activeScore" +
                score['dateTime'],
                title="activeScore of %s" %
                score['value'],
                source="fitbit",
                date=score['dateTime'],
                fulldata_json=score,
                update=True)
            lifestreamutils.newstat(
                score['dateTime'],
                "activeScore",
                score['value'])
