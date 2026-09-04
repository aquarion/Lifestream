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

    Only one OAuth flow can be in-flight at a time (matching the old
    CodeFetcher9000's single-listener-per-process constraint) — raises
    RuntimeError immediately if another flow is already waiting.

    Subscribes to the shared callback channel *before* advertising
    `key_wanted_arg` in Redis, so a callback can't arrive and get published
    with nobody listening yet. Returns the published params dict (same
    {key: [values]} shape urllib.parse.parse_qs produces) once a matching
    message arrives.

    Raises TimeoutError if nothing arrives within `timeout` seconds.
    """
    cxn = get_redis_connection()

    if cxn.get(OAUTH_KEY_WANTED_REDIS_KEY) is not None:
        raise RuntimeError(
            "Another OAuth callback flow is already in progress — "
            "only one at a time is supported."
        )

    pubsub = cxn.pubsub()
    pubsub.subscribe(OAUTH_CALLBACK_CHANNEL)

    # Wait for the subscribe confirmation so we know the subscription is
    # actually active before we set key_wanted below — otherwise a callback
    # arriving in that gap would be published with nobody listening yet,
    # and lost for good (Redis pub/sub does not buffer for late subscribers).
    confirmation = pubsub.get_message(timeout=timeout)
    if confirmation is None or confirmation.get("type") != "subscribe":
        pubsub.close()
        raise TimeoutError(
            "Timed out waiting to subscribe to the OAuth callback channel"
        )

    cxn.set(OAUTH_KEY_WANTED_REDIS_KEY, key_wanted_arg, ex=timeout)

    logger.info(
        "Waiting for OAuth callback (key=%s, timeout=%ss)", key_wanted_arg, timeout
    )

    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            message = pubsub.get_message(timeout=1.0)
            if message is None or message.get("type") != "message":
                continue
            try:
                params = json.loads(message["data"])
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "Ignoring malformed OAuth callback message: %r", message["data"]
                )
                continue
            if not isinstance(params, dict):
                continue
            if key_wanted_arg in params:
                return params
        raise TimeoutError(
            f"Timed out after {timeout}s waiting for OAuth callback "
            f"(key={key_wanted_arg})"
        )
    finally:
        cxn.delete(OAUTH_KEY_WANTED_REDIS_KEY)
        pubsub.close()
