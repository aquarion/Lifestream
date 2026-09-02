"""
Historic replay importer for Lifestream.

Finds posts made ten years ago (in a rolling 15-minute window) and replays
them. Tumblr posts are reblogged onto a dedicated "on this day" blog, queued
to go out at the same time of day ten years later; archived tweets are posted
to a dedicated Bluesky account, Twitter itself being long gone.
"""

import html
import json
import re
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

from atproto import Client as AtClient
from dateutil.relativedelta import relativedelta
from redis.exceptions import RedisError

from lifestream.core import (
    check_and_set_backoff,
    get_config_value,
    get_redis_connection,
)
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
REPLAY_KEY = "historic:replayed:{}"

# Twitter's own rendering of a retweet, which we replace with our own. Covers
# both the "RT @handle:" the retweet button produced and the "RT: @handle:" that
# clients typed by hand before it existed. The lookahead holds the handle to
# Twitter's 15 characters instead of quietly matching the first 15 of a longer
# run, which would attribute the post to somebody who does not exist.
RT_PREFIX_RE = re.compile(r"^RT:?\s+@([A-Za-z0-9_]{1,15})(?![A-Za-z0-9_]):?\s*")


def _defang(text: str) -> str:
    """
    Replace @ with 💬 in text about to be reposted.

    Kept from the Twitter era: a replayed post carrying its original
    @mentions would re-notify everyone named in it a decade later.
    """
    return text.replace("@", "💬")


def _clean(text: str) -> str:
    """
    Prepare stored tweet text for reposting.

    Twitter's API HTML-escapes what it returns and the importer stored it
    verbatim, so a tweet written with an ampersand sits in the database as
    "&amp;". Unescape before defanging, so that an escaped @ is defanged too.
    """
    return _defang(html.unescape(text))


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
    # "text" is what rows predating the extended tweet mode carry.
    body = retweeted.get("full_text") or retweeted.get("text")

    rendered = RT_PREFIX_RE.match(title)
    if rendered:
        handle = handle or rendered.group(1)
        body = body or title[rendered.end() :]

    if not handle:
        return _clean(title)

    # The sub is a no-op on a title with no prefix. It matters when the body
    # has fallen all the way back to the raw title, which would otherwise
    # repeat the attribution just added to the front of it.
    return f"[RT:💬{handle}] {_clean(body or RT_PREFIX_RE.sub('', title))}"


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
        self._atproto_unavailable = False

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

        Returns None when there is no usable account - none configured, or a
        login that failed - having said so once. A stale app password is not
        allowed to take down the Tumblr half of the same run.
        """
        if self._atproto or self._atproto_unavailable:
            return self._atproto

        username = get_config_value("historic", "atproto_username")
        password = get_config_value("historic", "atproto_password")
        if not username or not password:
            self.logger.warning(
                "Tweets from ten years ago are in this window, but no "
                "atproto_username/atproto_password is set in [historic]; "
                "skipping them"
            )
            self._atproto_unavailable = True
            return None

        server_base = get_config_value("historic", "atproto_server_base")
        try:
            client = AtClient(server_base) if server_base else AtClient()
            client.login(username, password)
        except Exception:
            self.logger.exception(
                "Could not log in to the Bluesky replay account; tweets in "
                "this window will be skipped, but the rest of the run goes on"
            )
            self._atproto_unavailable = True
            return None

        self._atproto = client
        return client

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
        Reserve a tweet for replay, returning False if it must not go out.

        The scheduler coalesces missed runs, so a catch-up can re-cover a
        window that has already fired. A second reblog of a Tumblr post is
        harmless; a second Bluesky post is just a duplicate post. A Redis that
        cannot answer refuses the claim too, but reports itself as what it is
        rather than as the tweet having already been posted.
        """
        try:
            claimed = not check_and_set_backoff(
                REPLAY_KEY.format(systemid), hours=REPLAY_MEMORY_HOURS
            )
        except RedisError:
            self.logger.exception(
                "Could not check whether tweet %s has already been replayed; "
                "skipping it rather than risk posting it twice",
                systemid,
            )
            return False

        if not claimed:
            self.logger.info("Skipping tweet %s, already replayed", systemid)
        return claimed

    def _release_replay(self, systemid) -> None:
        """
        Give a claim back when the post it was for did not happen.

        Claiming before posting is what stops a duplicate, but the claim would
        otherwise outlive the failure and make the tweet look replayed to any
        rerun of this window.
        """
        try:
            get_redis_connection().delete(REPLAY_KEY.format(systemid))
        except RedisError:
            self.logger.exception(
                "Could not release the replay claim on tweet %s; it will be "
                "skipped until the claim expires",
                systemid,
            )

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
            return

        # Rows imported before fulldata was stored have NULL here.
        data = json.loads(fulldata_json) if fulldata_json else None
        text = _tweet_text(title, data if isinstance(data, dict) else {})

        # Claimed before the post is shaped, so that a coalesced catch-up run
        # bails out here rather than re-reporting work it is not going to do.
        if not self._claim_replay(systemid):
            return

        if len(text) > MAX_POST_LENGTH:
            self.logger.warning(
                "Truncating tweet %s, %d characters is over the %d limit",
                systemid,
                len(text),
                MAX_POST_LENGTH,
            )
            text = text[: MAX_POST_LENGTH - 1] + "…"

        self.logger.info("Posting %r from %s", text, date_created)

        try:
            client.send_post(text=text)
        except Exception:
            self._release_replay(systemid)
            raise

    def _replay_row(self, row) -> bool:
        """
        Replay one row, returning False if it failed.

        A run covers fifteen minutes ten years back and the next run's window
        does not overlap it, so a row allowed to raise would take every row
        behind it out of the only run they were ever going to get.
        """
        title, date_created, url, fulldata_json, systemid, source, contenttype = row

        if not title:
            self.logger.info("Skipping, no content")
            return True

        try:
            if source == "tumblr":
                self._reblog_tumblr(
                    _defang(title), date_created, url, fulldata_json, systemid
                )
            elif contenttype == "twitter":
                self._replay_tweet(title, date_created, fulldata_json, systemid)
            else:
                # The query selects on exactly these two, so this is a warning
                # about the query and the dispatch having drifted apart.
                self.logger.warning(
                    "Skipping %s, nothing replays source %r type %r",
                    systemid,
                    source,
                    contenttype,
                )
        except Exception:
            self.logger.exception("Failed to replay %s", systemid)
            return False

        return True

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

        failed = [row[4] for row in rows if not self._replay_row(row)]

        if failed:
            raise RuntimeError(
                f"Failed to replay {len(failed)} of {len(rows)} historic "
                f"post(s): {', '.join(str(systemid) for systemid in failed)}"
            )


def main():
    """Entry point for CLI."""
    return HistoricImporter.main()


if __name__ == "__main__":
    exit(main())
