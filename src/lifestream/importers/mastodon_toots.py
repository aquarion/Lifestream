"""Mastodon toot importer for Lifestream."""

import argparse
import configparser
import sys

import mastodon as mastodonpy

from lifestream.importers.base import BaseImporter
from lifestream.core import config, force_json


class MastodonImporter(BaseImporter):
    """Import toots from Mastodon instances."""

    name = "mastodon"
    description = "Import toots from Mastodon instances"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add Mastodon-specific arguments."""
        parser.add_argument(
            "--site",
            required=False,
            help="Site to choose from",
            default=None,
        )
        parser.add_argument(
            "--all",
            required=False,
            help="Fetch all toots?",
            default=False,
            action="store_true",
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
        """Get list of Mastodon sites to process."""
        if self.args.site:
            return [self.args.site]

        sites = []
        for section in config.sections():
            if section.startswith("mastodon:"):
                sites.append(section[9:])
        return sites

    def process_site(self, site: str) -> None:  # noqa: C901
        """Process a single Mastodon site."""
        source = site
        entry_type = "mastodon"
        section = f"mastodon:{source}"

        try:
            base_url = config.get(section, "base_url")
            client_key = config.get(section, "client_key")
            client_secret = config.get(section, "client_secret")
            access_token = config.get(section, "access_token")
        except configparser.NoSectionError:
            self.logger.error(f"No [{section}] section found in config")
            sys.exit(5)
        except configparser.NoOptionError as e:
            self.logger.error(str(e))
            sys.exit(5)

        mastodon = mastodonpy.Mastodon(
            client_id=client_key,
            client_secret=client_secret,
            api_base_url=base_url,
            access_token=access_token,
        )

        this_page = 0
        keep_going = True

        how_are_you = mastodon.instance_health()
        if not how_are_you:
            self.logger.error(f"{site} is not fine")
            sys.exit(5)

        me = mastodon.me()
        last_seen = False

        while keep_going:
            if last_seen:
                toots = mastodon.account_statuses(me["id"], min_id=last_seen)
            else:
                toots = mastodon.account_statuses(me["id"])

            for toot in toots:
                title = toot["content"]

                thumbnail = ""
                if len(toot["media_attachments"]):
                    for media in toot["media_attachments"]:
                        if media["type"] == "image":
                            thumbnail = media["url"]
                            break

                self.entry_store.add_entry(
                    id=toot["id"],
                    title=title,
                    source=source,
                    date=toot["created_at"],
                    url=toot["url"],
                    image=thumbnail,
                    fulldata_json=force_json(toot),
                    type=entry_type,
                )

            if not len(toots):
                keep_going = False

            this_page += 1
            if this_page >= self.args.max_pages and not self.args.all_pages:
                keep_going = False
            elif not self.args.all_pages:
                self.logger.info(f"Page {this_page} of max {self.args.max_pages}")
            else:
                self.logger.info("Next Page...")

    def run(self) -> None:
        """Import toots from configured Mastodon sites."""
        sites = self.get_sites()

        if not sites:
            self.logger.error("No Mastodon sites configured")
            return

        for site in sites:
            self.logger.info(f"Processing site: {site}")
            self.process_site(site)


def main():
    """Entry point for CLI."""
    return MastodonImporter.main()


if __name__ == "__main__":
    exit(main())
