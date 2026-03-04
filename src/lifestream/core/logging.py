"""
Logging configuration for Lifestream.

Provides centralized logging setup with file and console handlers.
"""

import logging
import os
import sys
import warnings
from logging.handlers import TimedRotatingFileHandler

from .config import get_log_dir

_logging_configured = False

LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"


def setup_logging(
    debug: bool = False,
    verbose: bool = False,
    log_dir: str | None = None,
) -> None:
    """
    Configure logging for lifestream.

    Sets up file and console handlers. Call this once at startup.
    Safe to call multiple times (only configures once).

    Args:
        debug: Enable debug level logging
        verbose: Enable info level logging
        log_dir: Override log directory (uses config by default)
    """
    global _logging_configured
    if _logging_configured:
        return

    if log_dir is None:
        log_dir = str(get_log_dir())

    # Ensure log directory exists
    os.makedirs(log_dir, exist_ok=True)

    logging.getLogger("").setLevel(logging.WARNING)
    logging.captureWarnings(True)

    formatter = logging.Formatter(LOG_FORMAT)

    # File handler - weekly rotation
    filename = os.path.join(log_dir, "lifestream.log")
    logfile = TimedRotatingFileHandler(filename, when="W0", interval=1, utc=True)
    logfile.namer = lambda name: name.replace(".log", "") + ".log"
    logfile.setLevel(logging.DEBUG)
    logfile.setFormatter(formatter)
    logging.getLogger("").addHandler(logfile)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logging.getLogger("").addHandler(console_handler)

    # Set levels based on arguments
    if debug or "--debug" in sys.argv:
        console_handler.setLevel(logging.DEBUG)
        logging.getLogger("").setLevel(logging.DEBUG)
    elif verbose or "--verbose" in sys.argv:
        console_handler.setLevel(logging.INFO)
        logging.getLogger("").setLevel(logging.INFO)
    else:
        console_handler.setLevel(logging.ERROR)
        warnings.filterwarnings("ignore", category=DeprecationWarning, module="")

    _logging_configured = True


def get_logger(name: str) -> logging.Logger:
    """Get a logger with the given name."""
    return logging.getLogger(name)


def is_logging_configured() -> bool:
    """Check if logging has been configured."""
    return _logging_configured
