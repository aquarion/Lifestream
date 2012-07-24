#!/usr/bin/python
# -*- coding: utf-8 -*-
#
# Copyright 2010 Google Inc. All Rights Reserved.

"""Simple command-line example for Latitude.

Command-line application that sets the users
current location.
"""

__author__ = 'jcgregorio@google.com (Joe Gregorio)'

import gflags
import httplib2
import logging
import os
import pprint
import sys

from apiclient.discovery import build
from oauth2client.file import Storage
from oauth2client.client import AccessTokenRefreshError
from oauth2client.client import flow_from_clientsecrets
from oauth2client.tools import run


import lifestream
from datetime import datetime

dbcxn  = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)

SECRETS_FILE= lifestream.config.get("googleapi", "secrets_file")
CREDENTIALS = lifestream.config.get("latitude", "credentials_file")

FLAGS = gflags.FLAGS

# is missing.
MISSING_CLIENT_SECRETS_MESSAGE = """
WARNING: Please configure OAuth 2.0

To make this sample run you will need to populate the client_secrets.json file
found at:

   %s

with information from the APIs Console <https://code.google.com/apis/console>.

""" % os.path.join(os.path.dirname(__file__), SECRETS_FILE)


# Set up a Flow object to be used if we need to authenticate.
FLOW = flow_from_clientsecrets(SECRETS_FILE,
    scope='https://www.googleapis.com/auth/latitude.all.best',
    message=MISSING_CLIENT_SECRETS_MESSAGE)

def main(min_time = False, max_time = False):

  argv = sys.argv
  # Let the gflags module process the command-line arguments
  try:
    argv = FLAGS(argv)
  except gflags.FlagsError, e:
    print '%s\\nUsage: %s ARGS\\n%s' % (e, argv[0], FLAGS)
    sys.exit(1)

  storage = Storage(CREDENTIALS)
  credentials = storage.get()
  if credentials is None or credentials.invalid == True:
    credentials = run(FLOW, storage)

  http = httplib2.Http()
  http = credentials.authorize(http)

  service = build("latitude", "v1", http=http)

  #print service.currentLocation().insert(body=body).execute()
  
  if(min_time and max_time):
	  latitude_vague = service.location().list(granularity="city", max_results=1000, min_time=int(min_time), max_time=int(max_time)).execute()
	  latitude_best  = service.location().list(granularity="best", max_results=1000, min_time=int(min_time), max_time=int(max_time)).execute()
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
	
  #print n," items added"
  
def import_old_items():
  may = datetime(2010,5,1,0,0) # Earliest date to start from
  may_microseconds = time.mktime(may.timetuple()) * 1000
  two_weeks = 60*60*24*14*1000
  now = time.mktime(datetime.now().timetuple()) * 1000
  print may_microseconds
  startime = may_microseconds
  endtime = startime + two_weeks
  while startime < now:
    print datetime.fromtimestamp(startime/1000), datetime.fromtimestamp(endtime/1000)
    startime = startime + two_weeks
    endtime  = endtime  + two_weeks
    main(startime, endtime);

if __name__ == '__main__':
  main();
