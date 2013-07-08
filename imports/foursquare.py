#!/usr/bin/python

import lifestream
import sys
import os
import pytz
import re
from datetime import datetime

import oauth2
from twitter.oauth import write_token_file, read_token_file
import requests

from pprint import pprint

if (len(sys.argv) < 3):
	print "Usage: lifestreamit class username"
	sys.exit(5)

type = sys.argv[1]
username = sys.argv[2]
url = "http://foursquare.com/%s" % username

#DB Setup

dbcxn  = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)


#Oauth Setup

OAUTH_FILENAME  = os.environ.get('HOME', '') + os.sep + '.foursquare_oauth_'+username
CONSUMER_KEY    = lifestream.config.get("foursquare", "client_id")
CONSUMER_SECRET = lifestream.config.get("foursquare", "secret")

if not os.path.exists(OAUTH_FILENAME):
	print "You need to run foursquare_oauth.py to generate the oauth key"
	sys.exit(5)

oauth_token, oauth_token_secret = read_token_file(OAUTH_FILENAME)


# Loop setup

s_sql = u'replace into lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`, `image`) values (%s, %s, %s, %s, %s, %s, %s);'

l_sql = u'replace into lifestream_locations (`id`, `source`, `lat`, `long`, `lat_vague`, `long_vague`, `timestamp`, `accuracy`, `title`, `icon`) values (%s, "foursquare", %s, %s, %s, %s, %s, 1, %s, %s);'
  

URL_BASE = "https://api.foursquare.com/v2/%%s?oauth_token=%s" % oauth_token

# Get the data 

r = requests.get(URL_BASE% "users/self/checkins")

data = r.json()

checkins = data['response']['checkins']['items']


if 'checkins' in data['response'].keys():
	for location in checkins:
	    source = "Foursquare";
	    if "isMayor" in location.keys() and location['isMayor']:
		source = "Foursquare-Mayor"
		
	    image = ""

	    source = re.sub(r'<[^>]*?>', '', source) 

	    if "venue" in location.keys():
		message = location['venue']['name']
		if len(location['venue']['categories']):
		    for category in location['venue']['categories']:
			if "primary" in category.keys():
			    image = category['icon']
	    else:
		message = location['location']['name']

		
	    epoch = location['createdAt']
	    localzone = pytz.timezone(location['timeZone'])
	    localtime = localzone.localize(datetime.utcfromtimestamp(epoch))
	    utcdate = localtime.strftime("%Y-%m-%d %H:%M")
	    
	    id = location['id']

	    cursor.execute(s_sql, (type, id, message, utcdate, url, source, image))

	    coordinates = location['venue']['location']

	    #                     (`id`,  `lat`,            `long`, `lat_vague`, `long_vague`, `timestamp`, `title`, `icon`)
	    cursor.execute(l_sql, (epoch, coordinates['lat'], coordinates['lng'], coordinates['lat'], coordinates['lng'], utcdate, location['venue']['name'], image))


r = requests.get(URL_BASE% "users/self/badges")

data = r.json()

badges = data['response']['badges']

for badgeid, badge in badges.items():
        
    if len(badge['unlocks']) == 0:
        continue
    
    source  = "Foursquare-Badge";
    message = badge['name']
    image   = badge['image']['prefix']+ "%s" % badge['image']['sizes'][1] +badge['image']['name']
        
    checkin = badge['unlocks'][0]['checkins'][0]
    id      = checkin['id']

    epoch = checkin['createdAt']
    localzone = pytz.timezone(checkin['timeZone'])
    localtime = localzone.localize(datetime.utcfromtimestamp(epoch))
    utcdate = localtime.strftime("%Y-%m-%d %H:%M")

    cursor.execute(s_sql, (type, id, message, utcdate, url, source, image))
