"""Generic Atom/RSS feed importer for Lifestream."""

import argparse
from datetime import datetime
from time import mktime

import feedparser

from lifestream.importers.base import FeedImporter


class AtomImporter(FeedImporter):
    """Import entries from an Atom/RSS feed."""

    name = "atom"
    description = "Import entries from an Atom/RSS feed"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add feed-specific arguments."""
        parser.add_argument(
            "type",
            help="The type/source name for entries",
        )
        parser.add_argument(
            "url",
            help="The feed URL to import from",
        )

    def run(self) -> None:
        """Import entries from the feed."""
        entry_type = self.args.type
        url = self.args.url

        self.logger.info("Grabbing %s", url)
        fp = feedparser.parse(url)

        for o_item in fp["entries"]:
            item_id = o_item["guid"]
            dt = datetime.fromtimestamp(mktime(o_item["updated_parsed"]))
            updated = dt.strftime("%Y-%m-%d %H:%M")

            self.logger.info("Adding new %s item: %s", entry_type, o_item["title"])

            self.entry_store.add_entry(
                type=entry_type,
                id=item_id,
                title=o_item["title"],
                source=entry_type,
                date=updated,
                url=o_item["links"][0]["href"],
            )


def main():
    """Entry point for CLI."""
    return AtomImporter.main()


if __name__ == "__main__":
    exit(main())
