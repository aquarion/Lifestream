"""Caching functionality for Lifestream."""

import logging
import os
import pickle
import time

import redis

from . import config

# Module-level Redis connection (lazy initialized)
_redis_connection = None


def get_redis_connection():
    """Get a Redis connection using config settings."""
    global _redis_connection
    if _redis_connection is None:
        _redis_connection = redis.Redis(
            host=config.get("redis", "host", fallback="localhost"),
            port=int(config.get("redis", "port", fallback=6379)),
            username=config.get("redis", "username", fallback=None),
            password=config.get("redis", "password", fallback=None),
        )
    return _redis_connection


def set_backoff(warning_id, hours=24):
    """Mark a warning ID as recently sent, preventing duplicates for `hours`."""
    cxn = get_redis_connection()
    cxn.set(warning_id, "1", ex=hours * 3600)


def should_backoff(warning_id):
    """Check if we should back off from sending a warning."""
    cxn = get_redis_connection()
    return bool(cxn.get(warning_id))


def check_and_set_backoff(warning_id, hours=24):
    """
    Check if a warning was sent recently, and mark it if not.

    Returns:
        False if the warning was not sent recently (and has now been marked)
        TTL in seconds if the warning was sent recently
    """
    cxn = get_redis_connection()
    if not cxn.get(warning_id):
        cxn.set(warning_id, "1", ex=hours * 3600)
        return False
    else:
        return cxn.ttl(warning_id)


def file_cache(cache_id, maxage):
    """
    A decorator that caches function results to a file.

    Args:
        cache_id: Identifier for the cache file (stored in /tmp/)
        maxage: Maximum age of cache in seconds

    Returns:
        Decorator function
    """

    def decorator(fn):
        def wrapped(*args, **kwargs):
            cachefile = "/tmp/" + cache_id
            logger = logging.getLogger("file_cache")

            if os.path.exists(cachefile):
                modified = os.path.getmtime(cachefile)
                logger.debug(f"Found cache file at '{cachefile}'")
                now = time.time()
                if now > (modified + maxage):
                    logger.debug(f"Ignoring old cache file '{cachefile}'")
                else:
                    with open(cachefile, "rb") as cachehandle:
                        logger.info(f"Using cached result from '{cachefile}'")
                        return pickle.load(cachehandle)

            res = fn(*args, **kwargs)

            with open(cachefile, "wb") as cachehandle:
                logger.info(f"Saving result to cache '{cachefile}'")
                pickle.dump(res, cachehandle)

            return res

        return wrapped

    return decorator


# Aliases for backward compatibility
i_said_back_off = set_backoff
i_should_back_off = should_backoff
