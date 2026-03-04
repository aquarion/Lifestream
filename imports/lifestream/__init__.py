"""
Lifestream - A personal data aggregation system.

This module provides the core functionality for importing data from various
sources into a central database.
"""

import argparse
import configparser
import logging
import os
import sys
import warnings
from logging.handlers import TimedRotatingFileHandler

import pymysql as MySQLdb

# Libraries - re-exported for backward compatibility
from .oauth_utils import read_token_file, write_token_file  # noqa: F401

# Suppress MySQL warnings as errors
warnings.filterwarnings("error", category=MySQLdb.Warning)

# Path resolution
basedir = os.path.dirname(os.path.abspath(sys.argv[0]))
project_root = os.path.normpath(os.path.join(basedir, ".."))

# Configuration - loaded once at import
config = configparser.ConfigParser()
_config_paths = [
    os.path.join(basedir, "..", "config.ini"),
    os.path.join(os.getcwd(), "..", "config.ini"),
]
for config_path in _config_paths:
    if os.path.exists(config_path):
        config.read(config_path)
        break


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


# Argument parsing
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
_logging_configured = False


def parse_args():
    """Parse command line arguments and store the result."""
    global _parsed_args
    _parsed_args = arguments.parse_args()
    return _parsed_args


def get_parsed_args():
    """Get the parsed arguments, or None if not yet parsed."""
    return _parsed_args


def setup_logging():
    """
    Configure logging for lifestream.

    Sets up file and console handlers. Call this once at startup.
    Safe to call multiple times (only configures once).
    """
    global _logging_configured
    if _logging_configured:
        return

    LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    LOG_DIR = get_log_dir()

    logging.getLogger("").setLevel(logging.WARNING)
    logging.captureWarnings(True)

    formatter = logging.Formatter(LOG_FORMAT)

    # File handler - weekly rotation
    filename = os.path.join(LOG_DIR, "lifestream.log")
    logfile = TimedRotatingFileHandler(filename, when="W0", interval=1, utc=True)
    logfile.namer = lambda name: name.replace(".log", "") + ".log"
    logfile.setLevel(logging.DEBUG)
    logfile.setFormatter(formatter)
    logging.getLogger("").addHandler(logfile)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logging.getLogger("").addHandler(console_handler)

    # Set levels based on command line args
    if "--debug" in sys.argv:
        console_handler.setLevel(logging.DEBUG)
        logging.getLogger("").setLevel(logging.DEBUG)
    elif "--verbose" in sys.argv:
        console_handler.setLevel(logging.INFO)
        logging.getLogger("").setLevel(logging.INFO)
    else:
        console_handler.setLevel(logging.ERROR)
        warnings.filterwarnings("ignore", category=DeprecationWarning, module="")

    _logging_configured = True


# Auto-configure logging when running as script (not when imported for testing)
if not os.environ.get("LIFESTREAM_TESTING"):
    setup_logging()


# Re-exports for backward compatibility
# TODO: Refactor to avoid late imports - see GitHub issue
from .db import EntryStore  # noqa: F401, E402
from .foursquare_api import FoursquareAPI  # noqa: F401, E402
from .utils import (  # noqa: F401, E402
    AnAttributeError,
    convertNiceTime,
    force_json,
    is_jsonable,
    niceTimeDelta,
    yearsago,
)
