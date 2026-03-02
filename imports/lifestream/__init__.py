# Python
import argparse
import codecs
import configparser
import hashlib
import logging
import os
import pickle
import site
import sys
import time
import warnings
from datetime import datetime, timedelta
from logging.handlers import TimedRotatingFileHandler
from pprint import pprint

import oauth2
import pymysql as MySQLdb
import pytz
import redis
import requests
import simplejson
import simplejson as json
from memcache import SERVER_MAX_KEY_LENGTH, SERVER_MAX_VALUE_LENGTH, Client

# Libraries
from .oauth_utils import read_token_file, write_token_file

# Local

RedisCXN = False

basedir = os.path.dirname(os.path.abspath(sys.argv[0]))
project_root = os.path.normpath(os.path.join(basedir, ".."))
site.addsitedir(basedir + "/../lib")

warnings.filterwarnings("error", category=MySQLdb.Warning)

# sys.stdout = codecs.getwriter('utf8')(sys.stdout)

config = configparser.ConfigParser()
try:
    config.read(basedir + "/../config.ini")
except IOError:
    config.read(os.getcwd() + "/../config.ini")
    
def resolve_path(path):
    """Resolve a path relative to the project root directory."""
    if os.path.isabs(path):
        return path
    return os.path.normpath(os.path.join(project_root, path))


def get_secrets_dir():
    """Get the secrets directory path, resolved relative to project root."""
    return resolve_path(config.get("global", "secrets_dir"))


def get_log_dir():
    """Get the log directory path, resolved relative to project root."""
    return resolve_path(config.get("global", "log_location"))

arguments = argparse.ArgumentParser()
arguments.add_argument(
    "--debug", required=False, help="Enable Debug", default=False, action="store_true"
)
arguments.add_argument(
    "--verbose",
    required=False,
    help="Enable Verbosity",
    default=False,
    action="store_true",
)
arguments.add_argument(
    "--no-db",
    required=False,
    help="Print database operations instead of executing them",
    default=False,
    action="store_true",
)

_parsed_args = None


def parse_args():
    """Parse command line arguments and store the result."""
    global _parsed_args
    _parsed_args = arguments.parse_args()
    return _parsed_args


def get_parsed_args():
    """Get the parsed arguments, or None if not yet parsed."""
    return _parsed_args


LOG_DIR = get_log_dir()

LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"


logging.getLogger("").setLevel(logging.WARNING)
logging.captureWarnings(True)

formatter = logging.Formatter(LOG_FORMAT)
filename = "%s/lifestream.log" % LOG_DIR
logfile = TimedRotatingFileHandler(filename, when="W0", interval=1, utc=True)
logfile.namer = lambda name: name.replace(".log", "") + ".log"
logfile.setLevel(logging.DEBUG)
logfile.setFormatter(formatter)
logging.getLogger("").addHandler(logfile)

consoleLogger = logging.StreamHandler()
consoleLogger.setFormatter(formatter)
logging.getLogger("").addHandler(consoleLogger)

if "--debug" in sys.argv:
    print("Debug mode enabled")
    consoleLogger.setLevel(logging.DEBUG)
    logging.getLogger("").setLevel(logging.DEBUG)
elif "--verbose" in sys.argv:
    consoleLogger.setLevel(logging.INFO)
    logging.getLogger("").setLevel(logging.INFO)
else:
    consoleLogger.setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="")


# Import database functionality - for backward compatibility
from .db import Lifestream, get_connection as getDatabaseConnection, get_cursor as cursor


def getRedisConnection():
    global RedisCXN
    if not RedisCXN:
        RedisCXN = redis.Redis(
            host=config.get("redis", "host", fallback="localhost"),
            port=config.get("redis", "port", fallback=6379),
            username=config.get("redis", "username", fallback=None),
            password=config.get("redis", "password", fallback=None),
        )

    return RedisCXN


def convertNiceTime(number, format):
    if format == "decimal" or format == "dec":
        return int(number)

    if format == "binary" or format == "bin":
        return Denary2Binary(number)

    if format == "hex" or format == "hexadecimal":
        print("Converting %s to hex" % number)
        return hex(int(number))

    if format == "oct" or format == "octal":
        print("Converting %s to oct" % number)
        return oct(int(number))

    if format == "roman" or format == "roman":
        print("Converting %s to roman" % number)
        return int_to_roman(int(number))

    return False


def yearsago(years, from_date=None):
    if from_date is None:
        from_date = datetime.now()
    try:
        return from_date.replace(year=from_date.year - years)
    except ValueError:
        # Must be 2/29!
        assert from_date.month == 2 and from_date.day == 29  # can be removed
        return from_date.replace(month=2, day=28, year=from_date.year - years)


def is_jsonable(x):
    try:
        json.dumps(x)
        return True
    except:
        return False


def force_json(incoming):
    if incoming is dict:
        outgoing = {}
        for key, value in incoming:
            outgoing[key] = force_json(incoming)
        return outgoing
    elif incoming is tuple or incoming is list:
        outgoing = []
        for value in incoming:
            outgoing.append(force_json(incoming))
        return outgoing
    else:
        if is_jsonable(incoming):
            return force_json(incoming)
        else:
            return str(incoming)
    raise Exception("Logic failure")


def i_said_back_off(warning_id, hours=24):
    redisCxn = getRedisConnection()
    redisCxn.set(warning_id, "1", ex=hours * 3600)


def i_should_back_off(warning_id):
    redisCxn = getRedisConnection()
    lastSent = redisCxn.get(warning_id)

    if lastSent:
        return True
    else:
        return False


class AnAttributeError(Exception):
    pass


def niceTimeDelta(delta_object, format="decimal"):

    if type(delta_object) is int:
        delta_object = timedelta(seconds=delta_object)

    try:
        years = 0
        days = delta_object.days
        hours = delta_object.seconds // 3600
        minutes = (delta_object.seconds // 60) % 60
        if days > 365:
            years = int(days / 365)
            days = int(days % 365)

    except AnAttributeError:
        years = int(delta_object / (60 * 60 * 24 * 365))
        remainder = delta_object % (60 * 60 * 24 * 365)
        days = int(remainder / (60 * 60 * 24))
        remainder = delta_object % (60 * 60 * 24)
        hours = remainder / (60 * 60)
        remainder = delta_object % (60 * 60)
        minutes = remainder / 60

    if int(years) == 1:
        years_message = "1 year, "
    elif years > 1:
        years_message = "%s years, " % convertNiceTime(years, format)
    else:
        years_message = ""

    if days < 7 and years == 0:
        hours = hours + (24 * days)
        days = 0

    # if (hours < 48 and years == 0 and days < 3):
    #   minutes = minutes + (60*hours)
    #   hours = 0;

    if int(days) == 1:
        days_message = "1 day, "
    elif days > 1:
        days_message = "%s days, " % days
    else:
        days_message = ""

    if int(hours) == 1:
        hours_message = "1 hour, "
    elif hours > 1:
        hours_message = "%s hours, " % hours
    else:
        hours_message = ""

    if int(minutes) == 1:
        minutes_message = "1 minute"
    elif minutes > 1:
        minutes_message = "%s minutes" % minutes
    else:
        minutes_message = ""

    string = years_message + days_message + hours_message + minutes_message

    if string == "":
        return "seconds"
    else:
        return string


class FoursquareAPI:

    url_base = "https://api.foursquare.com/v2/%s"

    payload = {}

    mc = False
    mcprefix = False

    def __init__(self, lifestream):
        OAUTH_FILENAME = lifestream.config.get("foursquare", "secrets_file")
        CONSUMER_KEY = lifestream.config.get("foursquare", "client_id")
        CONSUMER_SECRET = lifestream.config.get("foursquare", "secret")

        MEMCACHE_HOST = lifestream.config.get("memcache", "host")
        MEMCACHE_PORT = lifestream.config.get("memcache", "port")
        self.mcprefix = lifestream.config.get("memcache", "prefix")

        servers = ["%s:%s" % (MEMCACHE_HOST, MEMCACHE_PORT)]
        self.mc = Client(servers, debug=1)

        if not os.path.exists(OAUTH_FILENAME):
            logger.error("No OAUTH found at %s" % OAUTH_FILENAME)
            raise Exception(
                "You need to run foursquare_oauth.py to generate the oauth key"
            )

        oauth_token, oauth_token_secret = read_token_file(OAUTH_FILENAME)

        self.payload = {"v": "20170801", "oauth_token": oauth_token}

    def cache_get(self, url, params):
        m = hashlib.sha224()
        m.update(url)
        m.update(str(params))
        key = m.hexdigest()

        res = self.mc.get(key)
        if res:
            return json.loads(res)

        r = requests.get(self.url_base %
                         "users/self/checkins", params=self.payload)
        self.mc.set(key, json.dumps(r.json()))
        return r.json()

    def my_checkins(self):
        return self.cache_get(
            self.url_base % "users/self/checkins", params=self.payload
        )

    def search_near(self, lat, lng, intent="checkin", radius=50, limit=10):
        payload = self.payload
        payload["ll"] = "%s,%s" % (lat, lng)
        payload["intent"] = intent
        payload["radius"] = radius
        payload["limit"] = limit
        return self.cache_get(self.url_base % "venues/search", params=self.payload)
