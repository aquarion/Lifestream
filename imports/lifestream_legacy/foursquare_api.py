"""Foursquare API client library."""

import hashlib
import logging
import os

import redis
import requests
import simplejson as json

from . import config
from .cache import get_redis_connection
from .oauth_utils import read_token_file

logger = logging.getLogger(__name__)


class FoursquareAPI:

    url_base = "https://api.foursquare.com/v2/%s"

    payload: dict[str, str] = {}

    redis_client: redis.Redis | None = None
    cache_prefix: str = "lifestream:foursquare:"

    def __init__(self, lifestream=None):
        OAUTH_FILENAME = config.get("foursquare", "secrets_file")
        # CONSUMER_KEY and CONSUMER_SECRET stored in config but auth uses tokens

        self.redis_client = get_redis_connection()
        self.cache_prefix = (
            config.get("redis", "prefix", fallback="lifestream:") + "foursquare:"
        )

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
        key = self.cache_prefix + m.hexdigest()

        if self.redis_client:
            res = self.redis_client.get(key)
            if res:
                # Redis returns bytes, decode to string for json.loads
                data = res.decode("utf-8") if isinstance(res, bytes) else str(res)
                return json.loads(data)

        r = requests.get(url, params=params)
        if self.redis_client:
            # Cache for 1 hour
            self.redis_client.set(key, json.dumps(r.json()), ex=3600)
        return r.json()

    def my_checkins(self):
        return self.cache_get(
            self.url_base % "users/self/checkins", params=self.payload
        )

    def search_near(self, lat, lng, intent="checkin", radius=50, limit=10):
        payload = self.payload.copy()
        payload["ll"] = "%s,%s" % (lat, lng)
        payload["intent"] = intent
        payload["radius"] = str(radius)
        payload["limit"] = str(limit)
        return self.cache_get(self.url_base % "venues/search", params=payload)
