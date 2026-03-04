"""
Lifestream - A personal data aggregation system.

This package provides functionality for importing personal data from various
online services into a unified database.
"""

__version__ = "2.0.0"

# Re-export commonly used items for convenience
from lifestream.core.config import (
    config,
    get_secrets_dir,
    get_log_dir,
    get_project_root,
)
from lifestream.core.logging import setup_logging, get_logger
from lifestream.core.db import EntryStore, get_connection, get_cursor
from lifestream.core.cache import get_redis_connection, file_cache
from lifestream.core.utils import (
    niceTimeDelta,
    yearsago,
    force_json,
    is_jsonable,
    convertNiceTime,
    AnAttributeError,
)
__all__ = [
    # Config
    "config",
    "get_secrets_dir",
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
]
