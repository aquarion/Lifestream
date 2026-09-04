"""CodeFetcher9000 - the importer-CLI-process side of the OAuth callback
handoff with the Lifestream webserver.

The actual HTTP listener is the persistent webserver (see
lifestream.core.webserver, served by supervisor.py) — this module publishes
which callback key an importer is waiting for, then blocks on Redis pub/sub
until the webserver's /keyback/ route delivers the matching params.
"""

import configparser
import json
import logging
import time

from lifestream.core.cache import get_redis_connection
from lifestream.core.config import config

logger = logging.getLogger("CodeFetcher")

# Shared with lifestream.core.webserver — must match exactly.
OAUTH_KEY_WANTED_REDIS_KEY = "lifestream:oauth:key_wanted"
OAUTH_CALLBACK_CHANNEL = "lifestream:oauth:callback"

DEFAULT_TIMEOUT_SECONDS = 300


class WeSayNotToday(Exception):
    """Raised when the webserver isn't configured/available; callers should fall back."""

    pass


def get_url() -> str:
    """URL the OAuth provider should redirect the user's browser back to."""
    domain = config.get("webserver", "domain")
    return f"https://{domain}/keyback/"


def are_we_working() -> bool:
    """Check that the webserver is configured to build OAuth redirect URLs."""
    try:
        config.get("webserver", "domain")
    except configparser.Error as e:
        logger.error("Webserver not configured: %s", e)
        raise WeSayNotToday() from e
    return True


def get_code(key_wanted_arg: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> dict:
    """
    Block until the webserver's /keyback/ route delivers a callback matching
    `key_wanted_arg`.

    Sets `key_wanted_arg` in Redis so the webserver (a different process)
    knows what it's waiting for, subscribes to the shared callback channel,
    and returns the published params dict (same {key: [values]} shape
    urllib.parse.parse_qs produces) once a matching message arrives.

    Raises TimeoutError if nothing arrives within `timeout` seconds.
    """
    cxn = get_redis_connection()
    cxn.set(OAUTH_KEY_WANTED_REDIS_KEY, key_wanted_arg, ex=timeout)

    pubsub = cxn.pubsub()
    pubsub.subscribe(OAUTH_CALLBACK_CHANNEL)

    logger.info(
        "Waiting for OAuth callback (key=%s, timeout=%ss)", key_wanted_arg, timeout
    )

    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            message = pubsub.get_message(timeout=1.0)
            if message is None or message.get("type") != "message":
                continue
            params = json.loads(message["data"])
            if key_wanted_arg in params:
                return params
        raise TimeoutError(
            f"Timed out after {timeout}s waiting for OAuth callback "
            f"(key={key_wanted_arg})"
        )
    finally:
        cxn.delete(OAUTH_KEY_WANTED_REDIS_KEY)
        pubsub.close()
