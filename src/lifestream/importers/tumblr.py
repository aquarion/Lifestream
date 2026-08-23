"""Tumblr importer for Lifestream."""

import argparse
import urllib.parse

import dateutil.parser
import oauth2 as oauth
import pytz
from pytumblr import TumblrRestClient

from lifestream.importers.base import ConfigurationError, OAuthImporter

REQUEST_TOKEN_URL = "http://www.tumblr.com/oauth/request_token"
ACCESS_TOKEN_URL = "http://www.tumblr.com/oauth/access_token"
AUTHORIZE_URL = "http://www.tumblr.com/oauth/authorize"


def authenticate(importer: OAuthImporter) -> TumblrRestClient:
    """
    Run Tumblr's OAuth 1.0a flow for the given importer and return a client.

    Shared by TumblrImporter and HistoricImporter, which both authenticate
    against the same [tumblr] credentials and token file.
    """
    consumer_key = importer.get_config("consumer_key")
    consumer_secret = importer.get_config("secret_key")

    oauth_token = None if importer.args.reauth else importer.load_oauth_token()

    if not oauth_token:
        consumer = oauth.Consumer(consumer_key, consumer_secret)
        client = oauth.Client(consumer)
        resp, content = client.request(REQUEST_TOKEN_URL, "GET")
        if resp["status"] != "200":
            raise ConfigurationError(f"Invalid response {resp['status']}.")

        request_token = dict(urllib.parse.parse_qsl(content))
        # intentional: user must visit this URL to complete OAuth flow
        authorize_link = f"{AUTHORIZE_URL}?oauth_token={request_token['oauth_token']}"  # codeql[py/clear-text-logging-sensitive-data]
        print("Go to the following link in your browser:")
        print(authorize_link)
        print()

        accepted = "n"
        while accepted.lower() == "n":
            accepted = input("Have you authorized me? (y/n) ")
        oauth_verifier = input("What is the PIN? ")

        token = oauth.Token(
            request_token["oauth_token"], request_token["oauth_token_secret"]
        )
        token.set_verifier(oauth_verifier)
        client = oauth.Client(consumer, token)

        resp, content = client.request(ACCESS_TOKEN_URL, "POST")
        oauth_token = dict(urllib.parse.parse_qsl(content))
        importer.save_oauth_token(oauth_token)

    return TumblrRestClient(
        consumer_key,
        consumer_secret,
        oauth_token["oauth_token"],
        oauth_token["oauth_token_secret"],
    )


class TumblrImporter(OAuthImporter):
    """Import posts from Tumblr blogs."""

    name = "tumblr"
    description = "Import posts from Tumblr blogs"
    config_section = "tumblr"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add Tumblr-specific arguments."""
        super().add_arguments(parser)
        parser.add_argument(
            "--full-import",
            required=False,
            help="Import every post instead of just the most recent",
            default=False,
            action="store_true",
        )

    def validate_config(self) -> bool:
        """Ensure Tumblr credentials are configured."""
        missing = [
            k
            for k in ("consumer_key", "secret_key", "secrets_file", "blogs")
            if not self.get_config(k)
        ]
        if missing:
            self.logger.error(f"Missing Tumblr config keys: {', '.join(missing)}")
            return False
        return True

    def get_oauth_path(self) -> str:
        """Tumblr's OAuth token path is a configured file, not the default."""
        return self.get_config("secrets_file")

    @staticmethod
    def _post_title(post):
        post_type = post["type"]
        if post.get("title"):
            title = post["title"]
        elif "caption" in post:
            title = post["caption"]
        elif "text" in post:
            title = post["text"]
        elif "body" in post:
            title = post["body"]
        else:
            title = f"Tumblr {post_type}"
        if post_type == "quote":
            title = post["text"]
        return title

    def process_blog(self, tumblr, blog, full_import):
        """Import posts from a single Tumblr blog.

        Returns:
            True if the blog was imported successfully, False if fetching
            it failed.
        """
        self.logger.info(blog)

        details = tumblr.posts(blog)
        if "errors" in details:
            self.logger.error("Error fetching %s: %s", blog, details["meta"]["msg"])
            return False

        max_posts = details["blog"]["posts"] if full_import else 20
        startat = 0.0

        while startat < max_posts:
            details = tumblr.posts(blog, offset=startat, limit=20)
            if "errors" in details:
                self.logger.error("Error fetching %s: %s", blog, details["meta"]["msg"])
                return False
            startat += 20

            posts = details["posts"]
            self.logger.info(
                "%s %d/%d %.2f%%",
                blog,
                startat,
                max_posts,
                (startat / max_posts) * 100.0,
            )

            for post in posts:
                post_type = post["type"]
                localdate = dateutil.parser.parse(post["date"])
                utcdate = localdate.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")
                image = (
                    post["photos"][0]["original_size"]["url"]
                    if post_type == "photo"
                    else False
                )

                self.entry_store.add_entry(
                    post_type,
                    post["id"],
                    self._post_title(post),
                    "tumblr",
                    utcdate,
                    url=post["post_url"],
                    image=image,
                    fulldata_json=post,
                )

        return True

    def run(self) -> None:
        """Import posts from all configured Tumblr blogs."""
        full_import = self.args.full_import
        self.logger.info(
            "Full import" if full_import else "Importing most recent posts"
        )

        tumblr = authenticate(self)
        blogs = self.get_config("blogs").split(",")

        failed_blogs = [
            blog for blog in blogs if not self.process_blog(tumblr, blog, full_import)
        ]

        if failed_blogs:
            raise RuntimeError(
                f"Failed to import Tumblr blog(s): {', '.join(failed_blogs)}"
            )


def main():
    """Entry point for CLI."""
    return TumblrImporter.main()


if __name__ == "__main__":
    exit(main())
