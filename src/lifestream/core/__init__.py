"""
Core functionality for Lifestream.

This module provides:
- Configuration management
- Database access
- Caching with Redis
- Logging setup
- Utility functions
"""

from .cache import (
    check_and_set_backoff,
    file_cache,
    get_redis_connection,
    set_backoff,
    should_backoff,
)
from .config import (
    config,
    get_config_bool,
    get_config_value,
    get_credentials_dir,
    get_log_dir,
    get_project_root,
    resolve_path,
)
from .db import EntryStore, get_connection, get_cursor, get_no_db_mode, set_no_db_mode
from .logging import get_logger, is_logging_configured, setup_logging
from .notifications import (
    send_failure_email,
    send_failure_notifications,
    send_failure_slack,
)
from .oauth_utils import read_token_file, write_token_file
from .utils import (
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
    "get_project_root",
    "get_credentials_dir",
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
