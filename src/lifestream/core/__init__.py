"""
Core functionality for Lifestream.

This module provides:
- Configuration management
- Database access
- Caching with Redis
- Logging setup
- Utility functions
"""

from .config import (
    config,
    get_project_root,
    get_secrets_dir,
    get_log_dir,
    resolve_path,
    get_config_value,
    get_config_bool,
)
from .logging import setup_logging, get_logger, is_logging_configured
from .db import EntryStore, get_connection, get_cursor, set_no_db_mode, get_no_db_mode
from .cache import (
    get_redis_connection,
    set_backoff,
    should_backoff,
    check_and_set_backoff,
    file_cache,
)
from .utils import (
    niceTimeDelta,
    yearsago,
    force_json,
    is_jsonable,
    convertNiceTime,
    AnAttributeError,
)
from .oauth_utils import read_token_file, write_token_file
from .notifications import (
    send_failure_notifications,
    send_failure_email,
    send_failure_slack,
)

__all__ = [
    # Config
    "config",
    "get_project_root",
    "get_secrets_dir",
    "get_log_dir",
    "resolve_path",
    "get_config_value",
    "get_config_bool",
    # Logging
    "setup_logging",
    "get_logger",
    "is_logging_configured",
    # Database
    "EntryStore",
    "get_connection",
    "get_cursor",
    "set_no_db_mode",
    "get_no_db_mode",
    # Cache
    "get_redis_connection",
    "set_backoff",
    "should_backoff",
    "check_and_set_backoff",
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
    "send_failure_email",
    "send_failure_slack",
]
