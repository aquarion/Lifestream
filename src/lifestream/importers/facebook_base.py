"""Shared Facebook Graph API OAuth flow and post handling for Lifestream.

Used by FacebookPostsImporter (the authenticated user's own timeline) and
FacebookPageImporter (a single configured Facebook Page's posts) — both
share the same [facebook] app credentials, the same facebook.oauth token
file, and identical privacy-filtering/persistence logic for posts.
"""

import argparse
import configparser
import logging
from datetime import datetime, timedelta

import pymysql
import requests
from dateutil import parser as dtparser

from lifestream.core import check_and_set_backoff, code_fetcher
from lifestream.core import config as raw_config
from lifestream.importers.base import ConfigurationError, OAuthImporter

logger = logging.getLogger("Facebook")

GRAPH_API_VERSION = "v21.0"
GRAPH_API_BASE = f"https://graph.facebook.com/{GRAPH_API_VERSION}"

REQUEST_TOKEN_URL = "https://www.facebook.com/dialog/oauth"
EXTEND_TOKEN_URL = "https://graph.facebook.com/oauth/access_token"

# Both importers persist to and read from the same facebook.oauth token file
# (see oauth_filename below), so a single OAuth grant has to cover whatever
# either importer needs — there's no way to hold two differently-scoped
# tokens under one file. user_posts,user_status is the union of what the
# two legacy scripts requested individually.
OAUTH_SCOPE = "user_posts,user_status"


class FacebookBaseImporter(OAuthImporter):
    """Shared auth/config/persistence for the Facebook importers."""

    config_section = "facebook"
    oauth_filename = "facebook.oauth"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add the pagination arguments shared by both Facebook importers."""
        super().add_arguments(parser)
        parser.add_argument(
            "--pages",
            required=False,
            type=int,
            help="Number of pages to go back. 0 (or --all) to go forever",
            default=5,
        )
        parser.add_argument(
            "--all",
            required=False,
            help="Get all posts",
            default=False,
            action="store_true",
        )

    def validate_config(self) -> bool:
        """Ensure Facebook app credentials are configured."""
        missing = [k for k in ("appid", "secret") if not self.get_config(k)]
        if missing:
            self.logger.error(f"Missing Facebook config keys: {', '.join(missing)}")
            return False
        return True

    def _get_redirect_uri(self) -> tuple[str, bool]:
        """Return (redirect_uri, use_code_fetcher)."""
        try:
            code_fetcher.are_we_working()
            return code_fetcher.get_url(), True
        except code_fetcher.WeSayNotToday:
            try:
                base = raw_config.get("dayze", "base")
                return f"{base}/facebook/catch.php", False
            except configparser.Error as e:
                raise ConfigurationError(
                    "To catch an OAuth request, configure either "
                    "[CodeFetcher9000] or [dayze] in config.ini"
                ) from e

    def authenticate(self) -> dict:
        """
        Run Facebook's OAuth flow (via CodeFetcher9000 or a manual PIN) and
        return the token dict, refreshing/persisting it as needed.
        """
        appid = self.get_config("appid")
        secret = self.get_config("secret")

        oauth_token = None if self.args.reauth else self.load_oauth_token()
        if oauth_token:
            return oauth_token

        redirect_uri, use_code_fetcher = self._get_redirect_uri()

        # intentional: user must visit this URL to complete OAuth; contains
        # no secret, only the public appid, redirect_uri, and scope
        request_token_url = f"{REQUEST_TOKEN_URL}?client_id={appid}&redirect_uri={redirect_uri}&response_type=token&scope={OAUTH_SCOPE}"  # codeql[py/clear-text-logging-sensitive-data]
        print("Go to the following link in your browser:")
        print(request_token_url)
        print()

        if use_code_fetcher:
            oauth_redirect = code_fetcher.get_code("access_token")
            access_key = oauth_redirect["access_token"][0]
        else:
            print("If you configure CodeFetcher9000, this is a lot easier.")
            access_key = input("What is the PIN? ")

        extend_response = requests.get(
            EXTEND_TOKEN_URL,
            params={
                "grant_type": "fb_exchange_token",
                "client_id": appid,
                "client_secret": secret,
                "fb_exchange_token": access_key,
            },
            timeout=30,
        )
        extend_response.raise_for_status()
        oauth_token = extend_response.json()

        delta = timedelta(seconds=int(oauth_token["expires_in"]))
        oauth_token["expire_dt"] = datetime.now() + delta

        self.save_oauth_token(oauth_token)
        return oauth_token

    def check_token_expiry(self, credentials: dict) -> None:
        """Raise if the token has already expired; warn (with backoff) if it's close."""
        expire_dt = credentials.get("expire_dt")
        if expire_dt is None:
            raise ConfigurationError(
                "Facebook token has no expiry recorded — run with --reauth"
            )

        now = datetime.now()
        if expire_dt <= now:
            raise ConfigurationError(
                f"Facebook token expired {(now - expire_dt).days} days ago — "
                "run with --reauth"
            )

        delta = expire_dt - now
        if delta.days <= 7:
            if check_and_set_backoff("facebook:token:warning_sent", 86400):
                self.logger.info(
                    "Token will expire in %d days (already warned recently)",
                    delta.days,
                )
            else:
                self.logger.warning("Token will expire in %d days!", delta.days)
        else:
            self.logger.info("Token will expire in %d days", delta.days)

    def graph_get(self, access_token: str, path: str, **params) -> dict:
        """Call the Facebook Graph API and return the decoded JSON body."""
        params["access_token"] = access_token
        response = requests.get(f"{GRAPH_API_BASE}/{path}", params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def _load_filters(self) -> tuple[dict, set]:
        """Load the [facebook:filters] list-id -> name map and visible-filter names."""
        if not raw_config.has_section("facebook:filters"):
            return {}, set()
        filters = dict(raw_config.items("facebook:filters"))
        visible_raw = self.get_config("visible_filters", fallback="")
        visible_filters = {
            name.strip() for name in visible_raw.split(",") if name.strip()
        }
        return filters, visible_filters

    @staticmethod
    def _post_is_visible(
        post: dict, url: str, filters: dict, visible_filters: set
    ) -> bool:
        privacy = post["privacy"]["value"]
        if privacy != "CUSTOM":
            logger.info("... %s privacy post, vote KEEP", privacy)
            return True
        allow = post["privacy"].get("allow")
        if not allow:
            logger.info("Ignoring post %s due to an ad-hoc privacy filter", url)
            return False

        post_filter_ids = set(allow.split(","))
        if not set(filters.keys()) & post_filter_ids:
            logger.error("[ERROR] on %s - List ID %s not known", url, allow)
            return False

        for filter_id in post_filter_ids:
            if filter_id not in filters:
                logger.info("... Filter ID %s unidentified", filter_id)
            elif filters[filter_id] in visible_filters:
                logger.info("... [%s] filter post, vote KEEP", filters[filter_id])
            else:
                logger.info("... [%s] filter post, vote HIDE", filters[filter_id])
                return False
        return True

    def process_post(self, post: dict, profile: dict) -> None:
        """Filter and persist a single Facebook post."""
        if post.get("application", {}).get("namespace") == "twitter":
            return
        if post["privacy"]["value"] == "SELF":
            return

        url = "https://www.facebook.com/{}/posts/{}".format(
            profile["id"], post["id"].split("_")[1]
        )

        filters, visible_filters = self._load_filters()
        if not self._post_is_visible(post, url, filters, visible_filters):
            self.logger.info("... HIDE %s", url)
            return
        self.logger.info("... KEEP %s", url)

        image = post.get("picture", False)
        post.setdefault("message", "")
        dt = dtparser.parse(post["created_time"])

        try:
            self.entry_store.add_entry(
                post["type"],
                post["id"],
                post["message"],
                "facebook",
                dt,
                url=url,
                image=image,
                fulldata_json=post,
            )
        except pymysql.err.InternalError as e:
            if e.args[0] == 1366:
                self.logger.info(e)
            else:
                self.logger.error(e)

    def run_pagination(self, profile: dict, posts: dict) -> None:
        """
        Process a Graph API posts response and follow its pagination.

        Shared by FacebookPostsImporter and FacebookPageImporter — the only
        difference between them is which object's posts get fetched first;
        walking the resulting pages is identical for both.
        """
        infinite = self.args.pages == 0 or self.args.all
        page = 0
        while True:
            page += 1
            self.logger.info("Page %d", page)

            if "data" not in posts:
                raise RuntimeError(
                    f"Unexpected Facebook Graph API response (no 'data' key): {posts}"
                )

            for post in posts["data"]:
                self.process_post(post, profile)

            if not infinite and page >= self.args.pages:
                self.logger.info("Hit the page limit (%d), stopping", self.args.pages)
                break

            next_url = posts.get("paging", {}).get("next")
            if not next_url:
                self.logger.info("No more pages")
                break
            # Facebook returns a fully-qualified next-page URL with its own
            # access_token already embedded — fetch it as-is rather than
            # re-joining it onto GRAPH_API_BASE.
            next_response = requests.get(next_url, timeout=30)
            next_response.raise_for_status()
            posts = next_response.json()
