"""Facebook Page posts importer for Lifestream."""

import argparse

import requests

from lifestream.importers.facebook_base import FacebookBaseImporter


class FacebookPageImporter(FacebookBaseImporter):
    """Import posts from a single configured Facebook Page."""

    name = "facebook_page"
    description = "Import posts from a configured Facebook Page"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add Facebook-page-specific arguments."""
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
        """Ensure Facebook app credentials and a target page_id are configured."""
        if not super().validate_config():
            return False
        if not self.get_config("page_id"):
            self.logger.error("Missing Facebook config key: page_id")
            return False
        return True

    def run(self) -> None:
        """Fetch and store the configured Page's posts, following pagination."""
        credentials = self.authenticate()
        self.check_token_expiry(credentials)
        access_token = credentials["access_token"]

        page_id = self.get_config("page_id")
        profile = self.graph_get(access_token, page_id)
        posts = self.graph_get(
            access_token,
            f"{page_id}/posts",
            fields="application,message,type,privacy,status_type,source,"
            "properties,link,picture,created_time",
        )

        infinite = self.args.pages == 0 or self.args.all
        page = 0
        while True:
            page += 1
            self.logger.info("Page %d", page)

            for post in posts.get("data", []):
                self.process_post(post, profile)

            if not infinite and page >= self.args.pages:
                self.logger.info("Hit the page limit (%d), stopping", self.args.pages)
                break

            next_url = posts.get("paging", {}).get("next")
            if not next_url:
                self.logger.info("No more pages")
                break
            next_response = requests.get(next_url, timeout=30)
            next_response.raise_for_status()
            posts = next_response.json()


def main():
    """Entry point for CLI."""
    return FacebookPageImporter.main()


if __name__ == "__main__":
    exit(main())
