"""Instagram feed importer for Lifestream.

Uses the unofficial, unmaintained ``InstagramAPI`` package (not a project
dependency — install it separately if you need to run this importer).
"""

import argparse
from datetime import datetime

from lifestream.importers.base import BaseImporter, ConfigurationError


def _item_image(item):
    if "image_versions2" in item:
        return item["image_versions2"]["candidates"][0]["url"]
    if "carousel_media" in item:
        return item["carousel_media"][0]["image_versions2"]["candidates"][0]["url"]
    raise ValueError("No image thumbnail found")


class InstagramImporter(BaseImporter):
    """Import photo posts from Instagram."""

    name = "instagram"
    description = "Import photo posts from Instagram"
    config_section = "instagram"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add Instagram-specific arguments."""
        parser.add_argument(
            "--all",
            required=False,
            help="Get all items, not just the latest page",
            default=False,
            action="store_true",
        )

    def validate_config(self) -> bool:
        """Ensure Instagram credentials are configured."""
        missing = [k for k in ("username", "password") if not self.get_config(k)]
        if missing:
            self.logger.error(f"Missing Instagram config keys: {', '.join(missing)}")
            return False
        return True

    def _process_item(self, item) -> None:
        try:
            caption = item["caption"]["text"]
        except TypeError:
            caption = ""

        timestamp = datetime.fromtimestamp(item["taken_at"])
        url = f"https://instagram.com/p/{item['code']}"
        image = _item_image(item)
        self.logger.info("%s: %s", timestamp, caption)
        self.entry_store.add_entry(
            "photo",
            item["id"],
            caption,
            "instagram",
            timestamp,
            url=url,
            image=image,
            fulldata_json=item,
        )

    def run(self) -> None:
        """Log in and import the Instagram feed."""
        from InstagramAPI import InstagramAPI

        api = InstagramAPI(self.get_config("username"), self.get_config("password"))

        if not api.login():
            raise ConfigurationError("Instagram login failed")

        if self.args.all:
            feed = api.getTotalSelfUserFeed()
        else:
            feed = api.getSelfUserFeed()

        if not feed:
            raise ConfigurationError("Failed to get Instagram feed")

        if feed is True:
            feed = api.LastJson["items"]

        for item in feed:
            self._process_item(item)


def main():
    """Entry point for CLI."""
    return InstagramImporter.main()


if __name__ == "__main__":
    exit(main())
