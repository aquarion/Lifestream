#!/usr/bin/python

## Lifestream Kickstarter Module, by Aquarion <nicholas@aquarionics.com>
## 
## With invaluable help from http://syntaxi.net/2013/03/24/let-s-explore-kickstarter-s-api/
## 
## Released under the BSD licence.

import lifestream, lifestreamutils

import requests
import sys
from datetime import datetime, timedelta

Lifestream = lifestream.Lifestream()


## Kickstarter have not opened this up yet. Until then, you can get an access token via
## curl -X POST -d '{"password":"not-a-real-password","email":"not-a-real-email@example.com"}' https://api.kickstarter.com/xauth/access_token?client_id=2II5GGBZLOOZAA5XBU1U0Y44BU57Q58L8KOGM7H0E0YFHP3KTG

access_token  = lifestream.config.get("kickstarter", "access_token")

def kickstarter_call(call, token, payload={}):
	base_path = "https://api.kickstarter.com/v1/"
	payload['oauth_token'] = token 
	url = base_path+call;
	r = requests.get(url, params=payload)
	return r.json


kickstarter = kickstarter_call("users/self/projects/backed", access_token)

if not kickstarter.has_key("projects"):
	print kickstarter
	sys.exit(5)

for project in kickstarter['projects']:
	#date  = datetime.fromtimestamp(project['created_at'])
	date  = datetime.now()
	url   = project['urls']['web']['project'];
	photo = project['photo']['full']
	print project['name']
	Lifestream.add_entry(type="pledge", id=project['id'], title=project['name'], source="kickstarter", url=url, date=date, image=photo, fulldata_json=project)


#### This code is to "catch up" from kickstarter history, you should only need to do it once. Uncomment it when you do.

# cursor = 0;

# while kickstarter.has_key('urls') and kickstarter['urls'].has_key('api') and kickstarter['urls']['api'].has_key('more_projects'):
# 	cursor += 10;
# 	kickstarter = kickstarter_call("users/self/projects/backed", access_token, {'cursor' : cursor })
# 	print "--> From %s" % cursor; 
# 	if not kickstarter.has_key("projects"):
# 		print kickstarter
# 		sys.exit(5)
# 	for project in kickstarter['projects']:
# 		print project['name']
# 		date  = datetime.fromtimestamp(project['created_at'])
# 		url   = project['urls']['web']['project'];
# 		photo = project['photo']['full']
# 		Lifestream.add_entry(type="pledge", id=project['id'], title=project['name'], source="kickstarter", url=url, date=date, image=photo, fulldata_json=project)