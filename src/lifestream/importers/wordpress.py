"""WordPress posts importer for Lifestream.

Uses the WordPress REST API (built into WordPress core since 4.7) rather
than XML-RPC, which many hosts disable by default and which needed a
bitrotting third-party client library. Authenticates with an Application
Password (native since WordPress 5.6) sent as HTTP Basic auth.
"""

import argparse
import configparser

import dateutil.parser
import requests

from lifestream.core import config
from lifestream.importers.base import BaseImporter, ConfigurationError

POSTS_PATH = "/wp-json/wp/v2/posts"
PER_PAGE = 30


class WordpressImporter(BaseImporter):
    """Import posts from WordPress sites."""

    name = "wordpress"
    description = "Import posts from WordPress sites"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add WordPress-specific arguments."""
        parser.add_argument(
            "site",
            type=str,
            help="Site, as defined in config.ini",
            nargs="*",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            help="Fetch all posts?",
            dest="all_pages",
        )
        parser.add_argument(
            "--max_pages",
            type=int,
            help="How many pages (overridden by --all)",
            default=1,
            required=False,
        )

    def get_sites(self) -> list[str]:
        """Get list of WordPress sites to process."""
        if self.args.site:
            return self.args.site

        sites = []
        for section in config.sections():
            if section.startswith("wordpress:"):
                sites.append(section[10:])
        return sites

    @staticmethod
    def _post_title(post: dict) -> str:
        title = post["title"]["rendered"].strip()
        if title:
            return title
        excerpt = post["excerpt"]["rendered"].strip()
        if excerpt:
            return excerpt
        return "[Untitled Post]"

    @staticmethod
    def _post_thumbnail(post: dict) -> str:
        media = post.get("_embedded", {}).get("wp:featuredmedia")
        if not media:
            return ""
        return media[0].get("source_url", "")

    def _fetch_page(
        self, posts_url: str, auth: tuple, page: int, source: str
    ) -> requests.Response:
        """Fetch one page of posts, raising ConfigurationError on bad credentials."""
        response = requests.get(
            posts_url,
            params={
                "per_page": PER_PAGE,
                "page": page,
                "status": "publish",
                "_embed": 1,
            },
            auth=auth,
            timeout=30,
        )
        if response.status_code == 401:
            raise ConfigurationError(
                f"Invalid credentials for WordPress site '{source}': {response.text}"
            )
        response.raise_for_status()
        return response

    def process_site(self, site: str) -> None:
        """Process a single WordPress site."""
        source = site
        entry_type = "wordpress"
        section = f"wordpress:{source}"

        self.logger.info(site)

        try:
            url = config.get(section, "url")
            user = config.get(section, "username")
            passwd = config.get(section, "password")
        except configparser.NoSectionError:
            raise ConfigurationError(f"No [{section}] section found in config")
        except configparser.NoOptionError as e:
            raise ConfigurationError(str(e))

        posts_url = url.rstrip("/") + POSTS_PATH

        this_page = 0
        keep_going = True

        while keep_going:
            this_page += 1
            response = self._fetch_page(posts_url, (user, passwd), this_page, source)
            posts = response.json()
            # WordPress reports the total page count on every collection
            # response — a more reliable stop signal than waiting for an
            # empty page or the rest_post_invalid_page_number error a page
            # past the end returns.
            total_pages = int(response.headers.get("X-WP-TotalPages", "1") or "1")

            for post in posts:
                title = self._post_title(post)
                thumbnail = self._post_thumbnail(post)
                utcdate = dateutil.parser.parse(post["date_gmt"])

                self.entry_store.add_entry(
                    id=post["guid"]["rendered"],
                    title=title,
                    source=source,
                    date=utcdate.strftime("%Y-%m-%d %H:%M"),
                    url=post["link"],
                    image=thumbnail,
                    type=entry_type,
                )

                self.logger.info(f"{utcdate.strftime('%Y-%m-%d')}: {title}")

            if not posts or this_page >= total_pages:
                keep_going = False

            if this_page >= self.args.max_pages and not self.args.all_pages:
                keep_going = False
            elif not self.args.all_pages:
                self.logger.info(f"Page {this_page} of max {self.args.max_pages}")
            else:
                self.logger.info("Next Page...")

    def run(self) -> None:
        """Import posts from configured WordPress sites."""
        sites = self.get_sites()

        if not sites:
            raise ConfigurationError(
                "No WordPress sites configured — add [wordpress:sitename] sections to config.ini"
            )

        for site in sites:
            self.process_site(site)


def main():
    """Entry point for CLI."""
    return WordpressImporter.main()


if __name__ == "__main__":
    exit(main())
