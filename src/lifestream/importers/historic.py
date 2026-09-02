"""
Historic replay importer for Lifestream.

Finds posts made ten years ago (in a rolling 15-minute window) and replays
them. Tumblr posts are reblogged onto a dedicated "on this day" blog, queued
to go out at the same time of day ten years later; archived tweets are posted
to a dedicated Bluesky account, Twitter itself being long gone.
"""

import json
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from atproto import Client as AtClient
from dateutil.relativedelta import relativedelta

from lifestream.core import check_and_set_backoff, get_config_value
from lifestream.importers.base import OAuthImporter
from lifestream.importers.tumblr import authenticate

TEN_YEARS = relativedelta(years=10)
WINDOW = timedelta(minutes=15)
DEFAULT_TO_BLOG = "aquarions-of-history"

# Bluesky rejects records longer than this. Twitter was 140 characters for most
# of its life, so this will not bite until the 280-character era comes round,
# and then only for a retweet whose prefix pushes it over.
MAX_POST_LENGTH = 300

# How long a replayed tweet is remembered for. Only has to outlive the
# scheduler's misfire grace time.
REPLAY_MEMORY_HOURS = 24

# Twitter's own rendering of a retweet, which we replace with our own.
RT_PREFIX_RE = re.compile(r"^RT @([A-Za-z0-9_]+): ")


def _defang(text: str) -> str:
    """
    Replace @ with 💬 in text about to be reposted.

    Kept from the Twitter era: a replayed post carrying its original
    @mentions would re-notify everyone named in it a decade later.
    """
    return text.replace("@", "💬")


def _tweet_text(title: str, data: dict) -> str:
    """
    Work out what to post for an archived tweet.

    A retweet keeps its attribution as an explicit [RT:💬handle] prefix. Both
    that and the body are preferably read from the retweeted status, the title
    being Twitter's own rendering and truncated for a full-length retweet - but
    rows imported before fulldata was stored have nothing except that title, so
    fall back to reading the handle straight out of its "RT @handle: " prefix.
    """
    retweeted = data.get("retweeted_status") or {}
    handle = (retweeted.get("user") or {}).get("screen_name")
    body = retweeted.get("full_text")

    rendered = RT_PREFIX_RE.match(title)
    if rendered:
        handle = handle or rendered.group(1)
        body = body or title[rendered.end() :]

    if not handle:
        return _defang(title)

    return f"[RT:💬{handle}] {_defang(body or title)}"


SELECT_SQL = (
    "select title, date_created, url, fulldata_json, systemid, source, type "
    "from lifestream where (source = 'tumblr' or type = 'twitter') "
    "and date_created between %s and %s"
)


class HistoricImporter(OAuthImporter):
    """Replay Tumblr posts and tweets from ten years ago."""

    name = "historic"
    description = "Replay Tumblr posts and tweets from ten years ago"
    config_section = "tumblr"

    def __init__(self):
        """Set up the lazily-authenticated clients."""
        super().__init__()
        self._tumblr = None
        self._atproto = None
        self._warned_no_atproto = False

    @property
    def to_blog(self) -> str:
        """Tumblr blog that ten-year-old Tumblr posts are reblogged onto."""
        # `or` rather than a fallback: a blank tumblr_blog in the config file
        # is a key that exists, and reblogging onto "" is worse than the default.
        return get_config_value("historic", "tumblr_blog") or DEFAULT_TO_BLOG

    def validate_config(self) -> bool:
        """Ensure Tumblr credentials are configured."""
        missing = [
            k
            for k in ("consumer_key", "secret_key", "secrets_file")
            if not self.get_config(k)
        ]
        if missing:
            self.logger.error(f"Missing Tumblr config keys: {', '.join(missing)}")
            return False
        return True

    def get_oauth_path(self) -> str:
        """Historic reblogs share the [tumblr] OAuth token file."""
        return self.get_config("secrets_file")

    def tumblr_client(self):
        """Authenticate against Tumblr, on first use only."""
        if self._tumblr is None:
            self._tumblr = authenticate(self)
        return self._tumblr

    def atproto_client(self):
        """
        Log in to the Bluesky replay account, on first use only.

        Returns None when no account is configured, so a config that only
        wants the Tumblr half keeps working untouched.
        """
        if self._atproto is None:
            username = get_config_value("historic", "atproto_username")
            password = get_config_value("historic", "atproto_password")
            if not username or not password:
                return None
            server_base = get_config_value("historic", "atproto_server_base")
            client = AtClient(server_base) if server_base else AtClient()
            client.login(username, password)
            self._atproto = client
        return self._atproto

    def _is_own_post(self, data, url) -> bool:
        """
        Is this row a post that already lives on the history blog?

        Reblogs land there dated ten years after the original, the Tumblr
        importer picks them back up, and ten years later they would be
        reblogged onto the history blog all over again.
        """
        blog_name = data.get("blog_name")
        if blog_name:
            return blog_name == self.to_blog
        return urlparse(url or "").hostname == f"{self.to_blog}.tumblr.com"

    def _claim_replay(self, systemid) -> bool:
        """
        Reserve a tweet for replay, returning False if it already went out.

        The scheduler coalesces missed runs, so a catch-up can re-cover a
        window that has already fired. A second reblog of a Tumblr post is
        harmless; a second Bluesky post is just a duplicate post.
        """
        try:
            return not check_and_set_backoff(
                f"historic:replayed:{systemid}", hours=REPLAY_MEMORY_HOURS
            )
        except Exception:
            self.logger.exception(
                "Could not check whether tweet %s has already been replayed; "
                "skipping it rather than risk posting it twice",
                systemid,
            )
            return False

    def _reblog_tumblr(self, text, date_created, url, fulldata_json, systemid) -> None:
        """Reblog one ten-year-old Tumblr post onto the history blog."""
        if not fulldata_json:
            self.logger.info("Skipping %s, no fulldata", text)
            return

        data = json.loads(fulldata_json)

        if self._is_own_post(data, url):
            self.logger.info("Skipping %s, already on %s", text, self.to_blog)
            return

        self.logger.info("Reblogging %r from %s", text, date_created)

        self.tumblr_client().reblog(
            self.to_blog,
            id=systemid,
            reblog_key=data["reblog_key"],
            state="queue",
            date=date_created + TEN_YEARS,
        )

    def _replay_tweet(self, title, date_created, fulldata_json, systemid) -> None:
        """Post one ten-year-old tweet to the Bluesky replay account."""
        client = self.atproto_client()
        if client is None:
            if not self._warned_no_atproto:
                self.logger.warning(
                    "Tweets from ten years ago are in this window, but no "
                    "atproto_username/atproto_password is set in [historic]; "
                    "skipping them"
                )
                self._warned_no_atproto = True
            return

        text = _tweet_text(title, json.loads(fulldata_json) if fulldata_json else {})

        if len(text) > MAX_POST_LENGTH:
            self.logger.warning(
                "Truncating tweet %s, %d characters is over the %d limit",
                systemid,
                len(text),
                MAX_POST_LENGTH,
            )
            text = text[: MAX_POST_LENGTH - 1] + "…"

        if not self._claim_replay(systemid):
            self.logger.info("Skipping tweet %s, already replayed", systemid)
            return

        self.logger.info("Posting %r from %s", text, date_created)

        client.send_post(text=text)

    def run(self) -> None:
        """Replay posts from exactly ten years ago in this run's window."""
        now = datetime.now(UTC)
        date_from = now - TEN_YEARS
        date_to = date_from + WINDOW

        rows = []
        if not self.entry_store.no_db:
            with self.entry_store.dbcxn.cursor() as cursor:
                cursor.execute(SELECT_SQL, (date_from.isoformat(), date_to.isoformat()))
                rows = cursor.fetchall()

        if not rows:
            self.logger.info("Nothing posted in this window ten years ago")
            return

        for row in rows:
            title, date_created, url, fulldata_json, systemid, source, contenttype = row

            if not title:
                self.logger.info("Skipping, no content")
                continue

            if source == "tumblr":
                self._reblog_tumblr(
                    _defang(title), date_created, url, fulldata_json, systemid
                )
            elif contenttype == "twitter":
                self._replay_tweet(title, date_created, fulldata_json, systemid)
            else:
                self.logger.debug(
                    "Skipping %s, nothing replays source %r type %r",
                    systemid,
                    source,
                    contenttype,
                )


def main():
    """Entry point for CLI."""
    return HistoricImporter.main()


if __name__ == "__main__":
    exit(main())
