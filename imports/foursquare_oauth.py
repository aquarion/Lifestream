import json
import pprint
import os
import sys
import ConfigParser
from httplib2 import Http

OAUTH_BASE = "https://foursquare.com/oauth2/authenticate"

CLIENT_ID = ""
CLIENT_SECRET = ""
CALLBACK_URL = ""

FS_ACCESS_CODE = ""
FS_ACCESS_TOKEN = ""

if (len(sys.argv) < 2):
        print "Usage: %s username" % sys.argv[0]
        sys.exit(5)

username = sys.argv[1]

if len(sys.argv) == 3:
	FS_ACCESS_CODE=sys.argv[2]

basedir = os.path.dirname(os.path.abspath(sys.argv[0]))
config = ConfigParser.ConfigParser()
config.readfp(open(basedir+'/../config.ini'))

OAUTH_FILENAME = os.environ.get('HOME', '') + os.sep + '.foursquare_oauth_'+username
CLIENT_ID = config.get("foursquare", "client_id")
CLIENT_SECRET = config.get("foursquare", "secret")
CALLBACK_URL="www.github.com/aquarion/lifestream"


print CLIENT_ID

if not CLIENT_ID:
  print "=== Register your Foursquare data here"
  print "=== Copy back CLIENT_ID, CLIENT_SECRET and CALLBACK_URL here"
  print "https://foursquare.com/oauth/"
elif not FS_ACCESS_CODE:
  print "=== Enter this URL in your browser."
  print "=== Copy the CODE in the URL that results and run %s %s [code]" % (sys.argv[0], sys.argv[1])

  print "https://foursquare.com/oauth2/authenticate?client_id=%s&response_type=code&redirect_uri=%s" % (CLIENT_ID, CALLBACK_URL)

else:
	url="https://foursquare.com/oauth2/access_token?client_id=%s&client_secret=%s&grant_type=authorization_code&redirect_uri=%s&code=%s" % (CLIENT_ID, CLIENT_SECRET, CALLBACK_URL, FS_ACCESS_CODE)
	web = Http()
	resp, content = web.request(url)
	pprint.pprint(resp)
	pprint.pprint(content)
	
