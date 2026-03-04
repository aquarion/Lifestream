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
import requests
import simplejson
import simplejson as json

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


# Import database functionality
from .db import EntryStore

# Import utility functions for backward compatibility
from .utils import (
    AnAttributeError,
    convertNiceTime,
    force_json,
    is_jsonable,
    niceTimeDelta,
    yearsago,
)

# Import API clients for backward compatibility
from .foursquare_api import FoursquareAPI
