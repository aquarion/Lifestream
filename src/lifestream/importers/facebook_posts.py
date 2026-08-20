"""Facebook timeline posts importer for Lifestream."""

import argparse

import requests

from lifestream.importers.facebook_base import FacebookBaseImporter


class FacebookPostsImporter(FacebookBaseImporter):
    """Import posts from the authenticated user's own Facebook timeline."""

    name = "facebook_posts"
    description = "Import posts from the authenticated user's Facebook timeline"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add Facebook-posts-specific arguments."""
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

    def run(self) -> None:
        """Fetch and store the user's own posts, following pagination."""
        credentials = self.authenticate()
        self.check_token_expiry(credentials)
        access_token = credentials["access_token"]

        profile = self.graph_get(access_token, "me")
        posts = self.graph_get(
            access_token,
            "me/posts",
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
            # Facebook returns a fully-qualified next-page URL with its own
            # access_token already embedded — fetch it as-is rather than
            # re-joining it onto GRAPH_API_BASE.
            next_response = requests.get(next_url, timeout=30)
            next_response.raise_for_status()
            posts = next_response.json()


def main():
    """Entry point for CLI."""
    return FacebookPostsImporter.main()


if __name__ == "__main__":
    exit(main())
