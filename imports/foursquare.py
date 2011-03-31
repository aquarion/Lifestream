#!/usr/bin/python
import codecs, sys, os
import ConfigParser, MySQLdb, socket

import pytz

import re

from datetime import datetime

import oauth2
from twitter.oauth import write_token_file, read_token_file
import json
import httplib2

from pprint import pprint

sys.stdout = codecs.getwriter('utf8')(sys.stdout)

basedir = os.path.dirname(os.path.abspath(sys.argv[0]))
config = ConfigParser.ConfigParser()
config.readfp(open(basedir+'/../dbconfig.ini'))
db = {}


for item in config.items("database"):
	db[item[0]] = item[1]

dbcxn = MySQLdb.connect(user = db['username'], passwd = db['password'], db = db['database'], host = db['hostname'])
cursor = dbcxn.cursor()

if (len(sys.argv) < 3):
	print "Usage: lifestreamit class username"
	sys.exit(5)

type = sys.argv[1]
username = sys.argv[2]

url = "http://foursquare.com/%s" % username

s_sql = u'replace into lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`, `image`) values (%s, %s, %s, %s, %s, %s, %s);'

OAUTH_FILENAME = os.environ.get('HOME', '') + os.sep + '.foursquare_oauth_'+username
CONSUMER_KEY = config.get("foursquare", "client_id")
CONSUMER_SECRET = config.get("foursquare", "secret")

if not os.path.exists(OAUTH_FILENAME):
	print "You need to run foursquare_oauth.py to generate the oauth key"
	sys.exit(5)


oauth_token, oauth_token_secret = read_token_file(OAUTH_FILENAME)

URL_BASE = "https://api.foursquare.com/v2/%%s?oauth_token=%s" % oauth_token
web = httplib2.Http()

 
response, content = web.request(URL_BASE% "users/self/checkins")
data = json.loads(content)
checkins = data['response']['checkins']['items']

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

    #print utcdate, message, localzone
    cursor.execute(s_sql, (type, id, message, utcdate, url, source, image))

response, content = web.request(URL_BASE% "users/self/badges")
data = json.loads(content)
badges = data['response']['badges']

for badgeid, badge in badges.items():
        
    if len(badge['unlocks']) == 0:
        continue
    
    source  = "Foursquare-Badge";
    message = badge['name']
    image   = badge['image']['prefix']+ "%s" % badge['image']['sizes'][1] +badge['image']['name']
        
    checkin = badge['unlocks'][0]['checkins'][0]
    id      = checkin['id']

    epoch = location['createdAt']
    localzone = pytz.timezone(location['timeZone'])
    localtime = localzone.localize(datetime.utcfromtimestamp(epoch))
    utcdate = localtime.strftime("%Y-%m-%d %H:%M")

    cursor.execute(s_sql, (type, id, message, utcdate, url, source, image))
    #print utcdate, message, image
