"""Facebook Page posts importer for Lifestream."""

from lifestream.importers.facebook_base import FacebookBaseImporter


class FacebookPageImporter(FacebookBaseImporter):
    """
    Import posts from a single configured Facebook Page.

    Note: the legacy imports/facebook_page.py this replaces had every
    entry_store.add_entry() call commented out — it only printed post
    messages and never persisted anything. This importer actually stores
    posts, the same as facebook_posts.py does. That's an intentional part
    of finishing the conversion (see issue #79), not an accidental side
    effect — the schedule entry in config.example.ini stays commented out
    until an operator deliberately enables it.
    """

    name = "facebook_page"
    description = "Import posts from a configured Facebook Page"

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

        self.run_pagination(profile, posts)


def main():
    """Entry point for CLI."""
    return FacebookPageImporter.main()


if __name__ == "__main__":
    exit(main())
