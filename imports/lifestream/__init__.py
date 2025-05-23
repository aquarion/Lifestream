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
site.addsitedir(basedir + "/../lib")

warnings.filterwarnings("error", category=MySQLdb.Warning)

# sys.stdout = codecs.getwriter('utf8')(sys.stdout)

config = configparser.ConfigParser()
try:
    config.read(basedir + "/../config.ini")
except IOError:
    config.read(os.getcwd() + "/../config.ini")

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

LOG_DIR = config.get("global", "log_location")

LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"

logging.getLogger("").setLevel(logging.DEBUG)

formatter = logging.Formatter(LOG_FORMAT)
filename = "%s/lifestream.log" % LOG_DIR
logfile = TimedRotatingFileHandler(filename, when="W0", interval=1, utc=True)
logfile.namer = lambda name: name.replace(".log", "") + ".log"
logfile.setLevel(logging.DEBUG)
logfile.setFormatter(formatter)
logging.getLogger("").addHandler(logfile)

console = logging.StreamHandler()
console.setFormatter(formatter)
logging.getLogger("").addHandler(console)

if "--debug" in sys.argv:
    console.setLevel(logging.DEBUG)
if "--verbose" in sys.argv:
    console.setLevel(logging.INFO)
else:
    console.setLevel(logging.ERROR)
    warnings.filterwarnings("ignore", category=DeprecationWarning, module="")


logger = logging.getLogger(__name__)


def getDatabaseConnection():

    db = {}
    for item in config.items("database"):
        db[item[0]] = item[1]

    dbcxn = MySQLdb.connect(
        user=db["username"],
        passwd=db["password"],
        db=db["database"],
        host=db["hostname"],
        charset="utf8mb4",
    )
    # dbcxn.set_character_set('utf8')
    return dbcxn


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


def cursor(dbcxn):
    dbc = dbcxn.cursor()
    dbc.execute("SET NAMES utf8mb4;")
    dbc.execute("SET CHARACTER SET utf8mb4;")
    dbc.execute("SET character_set_connection=utf8mb4;")

    return dbc


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


class Lifestream:

    dbcxn = False
    cursor = False
    config = False

    def __init__(self, *args, **kwargs):
        self.config = config

    def init_db(self):
        if self.dbcxn:
            return
        self.dbcxn = getDatabaseConnection()
        self.cursor = cursor(self.dbcxn)

    # Lifestream.add_entry(type, id, title, source, date, url='', image='', fulldata_json=False)
    def add_entry(
        self,
        type,
        id,
        title,
        source,
        date,
        url="",
        image="",
        fulldata_json=False,
        update=False,
        debug=False,
    ):

        self.init_db()

        if fulldata_json:
            fulldata_json = simplejson.dumps(fulldata_json)

        sql = "select date_created from lifestream where type = %s and systemid = %s order by date_created desc limit 1 "

        self.cursor.execute(sql, (type, str(id)))
        if self.cursor.fetchone():
            if not update:
                # print "Ignore - %s" % title
                return False
            else:
                # print "Update - %s" % title
                s_sql = "UPDATE lifestream set `title`=%s, `url`=%s, `date_created`=%s, `source`=%s, `image`=%s, `fulldata_json`=%s where `systemid`=%s and `type`=%s"
                self.cursor.execute(
                    s_sql, (title, url, date, source,
                            image, fulldata_json, id, type)
                )
                if debug:
                    print(self.cursor._executed)
        else:
            # print "Insert - %s" % title
            s_sql = "INSERT INTO lifestream (`type`, `systemid`, `title`, `url`, `date_created`, `source`, `image`, `fulldata_json`) values (%s, %s, %s, %s, %s, %s, %s, %s)"
            self.cursor.execute(
                s_sql, (type, id, title, url, date,
                        source, image, fulldata_json)
            )
            if debug:
                print(self.cursor._executed)

    def add_location(
        self, timestamp, source, lat, lon, title, icon=False, fulldata=False
    ):
        self.init_db()
        l_sql = 'replace into lifestream_locations (`id`, `source`, `lat`, `long`, `lat_vague`, `long_vague`, `timestamp`, `accuracy`, `title`, `icon`, `fulldata_json`) values (%s, %s, %s, %s, %s, %s, %s, 1, %s, %s, "");'
        time_start = datetime(1970, 1, 1, 0, 0, 0, 0, pytz.UTC)
        epoch = (timestamp - time_start).total_seconds()
        self.cursor.execute(
            l_sql,
            (
                epoch,  # `id`, `source`, `lat`, `long`, `lat_vague`, `long_vague`, `timestamp`, `accuracy`, `title`, `icon`,
                source,
                lat,
                lon,
                round(lat, 2),
                round(lon, 2),
                timestamp,
                title,
                icon,
            ),
        )

    def cache_this(self, cache_id, maxage):
        """
        A function that creates a decorator which will use "cachefile" for caching the results of the decorated function "fn".
        """

        def decorator(fn):  # define a decorator for a function "fn"
            # define a wrapper that will finally call "fn" with all arguments
            def wrapped(*args, **kwargs):
                cachefile = "/tmp/" + cache_id
                logger = logging.getLogger("cache_this")
                # if cache exists -> load it and return its content
                if os.path.exists(cachefile):
                    modified = os.path.getmtime(cachefile)
                    logger.debug("Found cache file at '{}'".format(cachefile))
                    now = time.time()
                    if now > (modified + maxage):
                        logger.debug(
                            "Ignoring old cache file {}'".format(cachefile))
                    else:
                        with open(cachefile, "rb") as cachehandle:
                            logger.info(
                                "using cached result from '{}'".format(
                                    cachefile)
                            )
                            return pickle.load(cachehandle)

                # execute the function with all arguments passed
                res = fn(*args, **kwargs)

                # write to cache file
                with open(cachefile, "wb") as cachehandle:
                    logger.info(
                        "saving result to cache '{}'".format(cachefile))
                    pickle.dump(res, cachehandle)

                return res

            return wrapped

        return decorator  # return this "customized" decorator that uses "cachefile"

    def warned_recently(self, warning_id, hours=24):
        redisCxn = getRedisConnection()
        lastSent = redisCxn.get(warning_id)

        if not lastSent:
            redisCxn.set(warning_id, "1", ex=hours * 3600)
            return False
        else:
            return redisCxn.ttl(warning_id)


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
