#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Simple command-line example for Latitude.

Command-line application that sets the users
current location.
"""

__author__ = 'jcgregorio@google.com (Joe Gregorio)'


from apiclient.discovery import build

import httplib2
import pickle

import time, datetime

from apiclient.discovery import build
from apiclient.oauth import FlowThreeLegged
from apiclient.ext.authtools import run
from apiclient.ext.file import Storage


import lifestream
from datetime import datetime

dbcxn  = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)

KEY         = lifestream.config.get("googleapi", "consumer_key")
SECRET      = lifestream.config.get("googleapi", "consumer_secret")
DOMAIN      = lifestream.config.get("googleapi", "domain")
CREDENTIALS = lifestream.config.get("latitude", "credentials_file")

# Uncomment to get detailed logging
# httplib2.debuglevel = 4

def main(min_time = False, max_time = False):
  storage = Storage(CREDENTIALS)
  credentials = storage.get()
  if credentials is None or credentials.invalid == True:
    auth_discovery = build("latitude", "v1").auth_discovery()
    flow = FlowThreeLegged(auth_discovery,
                           # You MUST have a consumer key and secret tied to a
                           # registered domain to use the latitude API.
                           #
                           # https://www.google.com/accounts/ManageDomains
                           consumer_key=KEY,
                           consumer_secret=SECRET,
                           user_agent='google-api-client-python-latitude/1.0',
                           domain=DOMAIN,
                           scope='https://www.googleapis.com/auth/latitude',
                           xoauth_displayname='Google API Latitude Example',
                           location='all',
                           granularity='best'
                           )

    credentials = run(flow, storage)

  http = httplib2.Http()
  http = credentials.authorize(http)

  service = build("latitude", "v1", http=http)

  #print service.currentLocation().insert(body=body).execute()
  
  if(min_time and max_time):
	  latitude_vague = service.location().list(granularity="city", max_results=1000, min_time=min_time, max_time=max_time).execute()
	  latitude_best  = service.location().list(granularity="best", max_results=1000, min_time=min_time, max_time=max_time).execute()
  else:
	  latitude_vague = service.location().list(granularity="city", max_results=1000).execute()
	  latitude_best  = service.location().list(granularity="best", max_results=1000).execute()
  
  s_sql = u'replace into lifestream_locations (`id`, `source`, `lat`, `long`, `lat_vague`, `long_vague`, `timestamp`, `accuracy`) values (%s, "latitude", %s, %s, %s, %s, %s, %s);'
  #{u'latitude': 51.552821000000002, u'kind': u'latitude#location', u'accuracy': 1414, u'longitude': 0.0070299999999999998, u'timestampMs': u'1333465871161'}
  
  n = 0
  
  previous = {'latitude' : 0, 'longitude' : 0}
  
  if not 'items' in latitude_best:
	print "No items found:"
	print latitude_vague
	print latitude_best
  else:
	for best in latitude_best['items']:
		if 'items' in latitude_vague:
			vague = False
			c = 0
			while vague == False:
				if not c in latitude_vague['items']:
					vague = "Failed"
				elif latitude_vague['items'][c]['timestampMs'] == best['timestampMs']:
					vague = latitude_vague['items'][c]
			
			if vague == "Failed":
				vague = {'latitude' : False, 'longitude' : False}
					
		else:
			vague = {'latitude' : False, 'longitude' : False}

		timestamp = datetime.fromtimestamp(float(best['timestampMs'])/1000)
		#print ".",
		if not best['latitude'] == previous['latitude'] and not best['longitude'] == previous['longitude']:
			#print best
			
			if 'accuracy' in best:
				accuracy = best['accuracy']
			else:
				accuracy = 0
			
			#                                (`id`,                 `lat`,             `long`,            `lat_vague`,   `long_vague`, `timestamp`, `accuracy`)
			cursor.execute(s_sql, (int(best['timestampMs']), 
				float(best['latitude']),  float(best['longitude']), 
				float(vague['latitude']), float(vague['longitude']), 
				timestamp, accuracy))

			previous = best
			n = n+1
	
  #rint n," items added"
  

if __name__ == '__main__':
  main();
