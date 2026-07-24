"""
Lifestream - A personal data aggregation system.

This package provides functionality for importing personal data from various
online services into a unified database.
"""

__version__ = "2.0.0"

# Expose core submodules so tests and callers can do `from lifestream import cache`
from lifestream.core import cache, db, jobs, notifications
from lifestream.core.cache import file_cache, get_redis_connection

# Re-export commonly used items for convenience
from lifestream.core.config import (
    config,
    get_credentials_dir,
    get_log_dir,
    get_project_root,
)
from lifestream.core.db import EntryStore, get_connection, get_cursor
from lifestream.core.logging import get_logger, setup_logging
from lifestream.core.notifications import send_failure_notifications
from lifestream.core.oauth_utils import read_token_file, write_token_file
from lifestream.core.utils import (
    AnAttributeError,
    convertNiceTime,
    force_json,
    is_jsonable,
    niceTimeDelta,
    yearsago,
)

__all__ = [
    # Config
    "config",
    "get_credentials_dir",
    "get_log_dir",
    "get_project_root",
    # Logging
    "setup_logging",
    "get_logger",
    # Database
    "EntryStore",
    "get_connection",
    "get_cursor",
    # Cache
    "get_redis_connection",
    "file_cache",
    # Utils
    "niceTimeDelta",
    "yearsago",
    "force_json",
    "is_jsonable",
    "convertNiceTime",
    "AnAttributeError",
    # OAuth
    "read_token_file",
    "write_token_file",
    # Notifications
    "send_failure_notifications",
    # Core submodules
    "cache",
    "db",
    "jobs",
    "notifications",
]
