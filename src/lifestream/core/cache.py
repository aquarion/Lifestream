"""Caching functionality for Lifestream."""

import json
import logging

import redis

from .config import config

# Module-level Redis connection (lazy initialized)
_redis_connection = None


def get_redis_connection():
    """Get a Redis connection using config settings."""
    global _redis_connection
    if _redis_connection is None:
        host = config.get("redis", "host", fallback="localhost")
        port = int(config.get("redis", "port", fallback=6379))
        conn = redis.Redis(
            host=host,
            port=port,
            username=config.get("redis", "username", fallback=None),
            password=config.get("redis", "password", fallback=None),
        )
        try:
            conn.ping()
        except redis.exceptions.AuthenticationError as e:
            raise redis.exceptions.AuthenticationError(
                f"Redis authentication failed — check redis.username/password in config: {e}"
            ) from e
        except redis.exceptions.ConnectionError as e:
            raise redis.exceptions.ConnectionError(
                f"Cannot connect to Redis at {host}:{port}: {e}"
            ) from e
        _redis_connection = conn
    return _redis_connection


def set_backoff(warning_id: str, hours: int = 24) -> None:
    """Mark a warning ID as recently sent, preventing duplicates for `hours`."""
    cxn = get_redis_connection()
    cxn.set(warning_id, "1", ex=hours * 3600)


def should_backoff(warning_id: str) -> bool:
    """Check if we should back off from sending a warning."""
    cxn = get_redis_connection()
    return bool(cxn.get(warning_id))


def check_and_set_backoff(warning_id: str, hours: int = 24) -> int | bool:
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


def redis_cache(cache_id: str, maxage: int):
    """
    A decorator that caches a function's JSON-serializable result in Redis.

    Args:
        cache_id: Redis key to store the cached result under
        maxage: Maximum age of the cached result in seconds (Redis TTL)

    Returns:
        Decorator function
    """

    def decorator(fn):
        def wrapped(*args, **kwargs):
            cxn = get_redis_connection()
            logger = logging.getLogger("redis_cache")

            cached = cxn.get(cache_id)
            if cached is not None:
                logger.info(f"Using cached result for '{cache_id}'")
                return json.loads(cached)

            res = fn(*args, **kwargs)
            logger.info(f"Saving result to cache '{cache_id}'")
            cxn.set(cache_id, json.dumps(res), ex=maxage)

            return res

        return wrapped

    return decorator
