"""Last.fm scrobble importer for Lifestream."""

import hashlib

import dateutil.parser
import feedparser
import pytz

from lifestream.importers.base import FeedImporter


class LastfmImporter(FeedImporter):
    """Import recent Last.fm scrobbles."""

    name = "lastfm"
    description = "Import recent Last.fm scrobbles"
    config_section = "lastfm"
    entry_type = "lastfm"
    source_name = "lastfm"

    def validate_config(self) -> bool:
        """Ensure username is configured."""
        username = self.get_config("username")
        if not username:
            self.logger.error("No Last.fm user found in config file")
            return False
        return True

    def get_feed_url(self) -> str:
        """Get the Last.fm RSS feed URL."""
        username = self.get_config("username")
        return f"https://xiffy.nl/lastfmrss.php?user={username}"

    def run(self) -> None:
        """Import recent Last.fm scrobbles."""
        url = self.get_feed_url()
        self.logger.info("Grabbing %s", url)

        fp = feedparser.parse(url)

        for i in range(1, len(fp["entries"])):
            o_item = fp["entries"][i]

            item_id = hashlib.md5()
            item_id.update(o_item["guid"].encode("utf-8"))

            title = o_item.title
            localdate = dateutil.parser.parse(o_item.updated)
            updated = localdate.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")

            # Remove unpicklable parsed date
            o_item_data = dict(o_item)
            if "published_parsed" in o_item_data:
                del o_item_data["published_parsed"]
            if "updated_parsed" in o_item_data:
                del o_item_data["updated_parsed"]

            self.logger.info(title)
            self.entry_store.add_entry(
                self.entry_type,
                item_id.hexdigest(),
                title,
                self.source_name,
                updated,
                url=o_item["link"],
                fulldata_json=o_item_data,
            )


def main():
    """Entry point for CLI."""
    return LastfmImporter.main()


if __name__ == "__main__":
    exit(main())
