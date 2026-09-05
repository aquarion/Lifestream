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
SUBSCRIBE_CONFIRMATION_TIMEOUT_SECONDS = 5


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


def _parse_callback_message(message) -> dict | None:
    """Extract the params dict from a pubsub message, or None if it's not a
    usable callback (wrong event type, malformed JSON, or not a dict)."""
    if message is None or message.get("type") != "message":
        return None
    try:
        params = json.loads(message["data"])
    except (json.JSONDecodeError, TypeError):
        logger.warning("Ignoring malformed OAuth callback message: %r", message["data"])
        return None
    return params if isinstance(params, dict) else None


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

    Raises TimeoutError if nothing arrives within `timeout` seconds total
    (this includes the brief wait for the subscribe confirmation, which is
    bounded separately and does not extend the overall budget).
    """
    cxn = get_redis_connection()

    # NOTE: this check-then-act guard has a TOCTOU race — two calls started
    # close together could both pass this check before either reaches set()
    # below, since set() isn't reached until after the subscribe-confirmation
    # wait (up to SUBSCRIBE_CONFIRMATION_TIMEOUT_SECONDS later), not
    # immediately after this check. Accepted for a personal single-user CLI
    # tool where OAuth flows are triggered manually, one at a time in
    # practice — not something concurrent/automated callers should rely on.
    if cxn.get(OAUTH_KEY_WANTED_REDIS_KEY) is not None:
        logger.warning(
            "Refusing to start OAuth flow (key=%s): another flow is already "
            "in progress. If this is stale, it clears automatically once the "
            "previous flow's timeout expires.",
            key_wanted_arg,
        )
        raise RuntimeError(
            "Another OAuth callback flow is already in progress — only one "
            "at a time is supported. If this is stale, it clears "
            "automatically once the previous flow's timeout expires."
        )

    deadline = time.monotonic() + timeout

    pubsub = cxn.pubsub()
    key_set = False
    try:
        pubsub.subscribe(OAUTH_CALLBACK_CHANNEL)

        # Bound the wait for the subscribe confirmation independently of the
        # overall timeout — Redis normally acks a SUBSCRIBE almost instantly,
        # so a short fixed cap keeps a slow/stuck ack from silently doubling
        # get_code()'s documented timeout.
        confirmation = pubsub.get_message(
            timeout=min(SUBSCRIBE_CONFIRMATION_TIMEOUT_SECONDS, timeout)
        )
        if confirmation is None or confirmation.get("type") != "subscribe":
            raise TimeoutError(
                "Timed out waiting to subscribe to the OAuth callback channel"
            )

        cxn.set(OAUTH_KEY_WANTED_REDIS_KEY, key_wanted_arg, ex=timeout)
        key_set = True

        logger.info(
            "Waiting for OAuth callback (key=%s, timeout=%ss)", key_wanted_arg, timeout
        )

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            message = pubsub.get_message(timeout=min(1.0, remaining))
            params = _parse_callback_message(message)
            if params is not None and key_wanted_arg in params:
                return params
        raise TimeoutError(
            f"Timed out after {timeout}s waiting for OAuth callback "
            f"(key={key_wanted_arg})"
        )
    finally:
        # Only clear the key if this call is the one that set it — otherwise,
        # if our own subscribe/confirmation step timed out before we ever
        # called set(), we could delete a DIFFERENT flow's key_wanted that
        # got set in the meantime (a different importer process's flow).
        if key_set:
            cxn.delete(OAUTH_KEY_WANTED_REDIS_KEY)
        pubsub.close()
