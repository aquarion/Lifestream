"""AT Protocol (Bluesky) posts importer for Lifestream."""

import argparse
import configparser
from urllib.parse import urlparse

import dateutil.parser
from atproto import Client as AtClient

from lifestream.core import config
from lifestream.importers.base import BaseImporter, ConfigurationError


def _get_thumbnail(embed):
    if embed and embed["py_type"] == "app.bsky.embed.images#viewImage":
        for media in embed.images:
            if media["py_type"] == "app.bsky.embed.images#viewImage":
                return media["thumb"]
    return ""


class AtprotoImporter(BaseImporter):
    """Import posts from one or more AT Protocol (Bluesky) accounts."""

    name = "atproto_posts"
    description = "Import posts from AT Protocol (Bluesky) accounts"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add AT Protocol-specific arguments."""
        parser.add_argument(
            "--site", required=False, help="Site to import (default: all configured)"
        )
        parser.add_argument(
            "--all",
            required=False,
            help="Fetch all posts, not just the first page(s)",
            default=False,
            action="store_true",
            dest="all_pages",
        )
        parser.add_argument(
            "--max_pages",
            type=int,
            help="How many pages to fetch (overridden by --all)",
            default=1,
            required=False,
        )

    def _get_sites(self) -> list[str]:
        if self.args.site:
            return [self.args.site]

        sites = []
        for section in config.sections():
            subsection = section.split(":")
            if subsection[0] == "atproto":
                sites.append(subsection[1])
        return sites

    def validate_config(self) -> bool:
        """Ensure at least one [atproto:site] section is configured."""
        if not self._get_sites():
            self.logger.error("No [atproto:site] sections found in config")
            return False
        return True

    def _process_post(self, item, site: str, handle: str) -> None:
        if item.post.author.handle != handle:
            self.logger.debug("Skipping retweet from %s", item.post.author.handle)
            return
        if item.post.record.reply:
            self.logger.debug("Skipping reply to %s", item.post.record.reply.parent.uri)
            return
        post = item.post.record
        date = dateutil.parser.isoparse(post.created_at)
        post_id = urlparse(item.post.uri).path.split("/")[2]
        url = f"https://{site}/profile/{handle}/post/{post_id}"
        self.entry_store.add_entry(
            id=item.post.uri,
            title=post.text,
            source=site,
            date=date,
            url=url,
            image=_get_thumbnail(item.post.embed),
            fulldata_json=item.post.model_dump_json(),
            type="atproto",
        )
        self.logger.info("%s: %s", date.strftime("%Y-%m-%d"), post.text)

    def _process_site(self, site: str) -> None:
        section = f"atproto:{site}"
        if not config.has_section(section):
            raise ConfigurationError(f"No [{section}] section found in config")

        try:
            username = config.get(section, "username")
            password = config.get(section, "password")
            handle = config.get(section, "handle")
            server_base = config.get(section, "server_base", fallback=None)
        except configparser.NoOptionError as e:
            raise ConfigurationError(f"Missing config in [{section}]: {e}") from e

        atserver = AtClient(server_base) if server_base else AtClient()
        atserver.login(username, password)

        this_page = 0
        keep_going = True
        last_seen = None

        while keep_going:
            if last_seen:
                response = atserver.get_author_feed(
                    actor=handle, cursor=last_seen, limit=30
                )
            else:
                response = atserver.get_author_feed(actor=handle, limit=30)

            last_seen = response.cursor

            for item in response.feed:
                self._process_post(item, site, handle)

            if not len(response.feed):
                self.logger.info("No more posts")
                keep_going = False

            this_page += 1
            if this_page >= self.args.max_pages and not self.args.all_pages:
                keep_going = False
                self.logger.info("Max pages (%d) reached", self.args.max_pages)
            elif not self.args.all_pages:
                self.logger.info("Page %d of max %d", this_page, self.args.max_pages)
            else:
                self.logger.info("Next page...")

    def run(self) -> None:
        """Import posts for each configured (or selected) site."""
        for site in self._get_sites():
            self._process_site(site)


def main():
    """Entry point for CLI."""
    return AtprotoImporter.main()


if __name__ == "__main__":
    exit(main())
