"""Foursquare API client library."""

import hashlib
import logging
import os

import requests
import simplejson as json
from memcache import Client

from . import config
from .oauth_utils import read_token_file

logger = logging.getLogger(__name__)


class FoursquareAPI:

    url_base = "https://api.foursquare.com/v2/%s"

    payload = {}

    mc = False
    mcprefix = False

    def __init__(self, lifestream=None):
        OAUTH_FILENAME = config.get("foursquare", "secrets_file")
        CONSUMER_KEY = config.get("foursquare", "client_id")
        CONSUMER_SECRET = config.get("foursquare", "secret")

        MEMCACHE_HOST = config.get("memcache", "host")
        MEMCACHE_PORT = config.get("memcache", "port")
        self.mcprefix = config.get("memcache", "prefix")

        servers = ["%s:%s" % (MEMCACHE_HOST, MEMCACHE_PORT)]
        self.mc = Client(servers, debug=1)

        if not os.path.exists(OAUTH_FILENAME):
            logger.error("No OAUTH found at %s" % OAUTH_FILENAME)
            raise Exception(
                "You need to run foursquare.py --reauth to generate the oauth key"
            )

        oauth_token, oauth_token_secret = read_token_file(OAUTH_FILENAME)

        self.payload = {"v": "20170801", "oauth_token": oauth_token}

    def cache_get(self, url, params):
        m = hashlib.sha224()
        m.update(url.encode("utf-8"))
        m.update(str(params).encode("utf-8"))
        key = m.hexdigest()

        res = self.mc.get(key)
        if res:
            return json.loads(res)

        r = requests.get(self.url_base % "users/self/checkins", params=self.payload)
        self.mc.set(key, json.dumps(r.json()))
        return r.json()

    def my_checkins(self):
        return self.cache_get(
            self.url_base % "users/self/checkins", params=self.payload
        )

    def search_near(self, lat, lng, intent="checkin", radius=50, limit=10):
        payload = self.payload.copy()
        payload["ll"] = "%s,%s" % (lat, lng)
        payload["intent"] = intent
        payload["radius"] = radius
        payload["limit"] = limit
        return self.cache_get(self.url_base % "venues/search", params=payload)
