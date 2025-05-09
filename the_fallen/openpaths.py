# Python
import json
import logging
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

import oauth2

# Local
import lifestream

# Libraries


logger = logging.getLogger("Openpaths")
args = lifestream.arguments.parse_args()

dbcxn = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)

ACCESS = lifestream.config.get("openpaths", "key")
SECRET = lifestream.config.get("openpaths", "secret")

URL = "https://openpaths.cc/api/1"


def build_auth_header(url, method):
    params = {
        "oauth_version": "1.0",
        "oauth_nonce": oauth2.generate_nonce(),
        "oauth_timestamp": str(int(time.time())),
    }
    consumer = oauth2.Consumer(key=ACCESS, secret=SECRET)
    params["oauth_consumer_key"] = consumer.key
    request = oauth2.Request(method=method, url=url, parameters=params)
    signature_method = oauth2.SignatureMethod_HMAC_SHA1()
    request.sign_request(signature_method, consumer, None)
    return request.to_header()


# GET data (last 24 hours)
now = time.time()

A_DAY = 24 * 60 * 60

params = {"start_time": now - A_DAY, "end_time": now}  # get the last 24 hours
query = "%s?%s" % (URL, urllib.parse.urlencode(params))

try:
    logger.debug("Grabbing %s" % URL)
    request = urllib.request.Request(query)
    request.headers = build_auth_header(URL, "GET")
    connection = urllib.request.urlopen(request)
    data = json.loads("".join(connection.readlines()))
except urllib.error.HTTPError as e:
    logger.error(e.read())
    sys.exit(5)

# [
#     {
#         "lon": -0.08443819731473923,
#         "device": "iPhone4,1",
#         "version": "1.1",
#         "t": 1377001728,
#         "lat": 51.49992370605469,
#         "alt": 18.485132217407227,
#         "os": "6.1.3"
#     }
# ]

previous = {"latitude": 0, "longitude": 0}

for datum in data:
    latitude_best = datum["lat"]
    latitude_vague = round(datum["lat"], 2)
    longitude_best = datum["lon"]
    longitude_vague = round(datum["lon"], 2)
    altitude_best = datum["alt"]
    altitude_vague = round(datum["alt"], 2)

    s_sql = 'replace into lifestream_locations (`id`, `source`, `lat`, `long`, `alt`, `lat_vague`, `long_vague`, `alt_vague`, `timestamp`, `accuracy`) values (%s, "openpaths", %s, %s, %s, %s, %s, %s, %s, %s);'
    # {u'latitude': 51.552821000000002, u'kind': u'latitude#location', u'accuracy': 1414, u'longitude': 0.0070299999999999998, u'timestampMs': u'1333465871161'}

    timestamp = datetime.fromtimestamp(datum["t"])
    # print ".",
    if (
        not latitude_best == previous["latitude"]
        and not longitude_vague == previous["longitude"]
    ):

        accuracy = 100
        logger.info("Found %s %s/%s" %
                    (timestamp, latitude_best, longitude_best))
        #                                (`id`,                 `lat`,             `long`,            `lat_vague`,   `long_vague`, `timestamp`, `accuracy`)
        cursor.execute(
            s_sql,
            (
                datum["t"],
                float(latitude_best),
                float(longitude_best),
                float(altitude_best),
                float(latitude_vague),
                float(longitude_vague),
                float(altitude_vague),
                timestamp,
                accuracy,
            ),
        )

        previous = {"latitude": latitude_best, "longitude": longitude_best}

dbcxn.close()
