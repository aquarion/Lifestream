"""Facebook timeline posts importer for Lifestream."""

from lifestream.importers.facebook_base import FacebookBaseImporter


class FacebookPostsImporter(FacebookBaseImporter):
    """Import posts from the authenticated user's own Facebook timeline."""

    name = "facebook_posts"
    description = "Import posts from the authenticated user's Facebook timeline"

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

        self.run_pagination(profile, posts)


def main():
    """Entry point for CLI."""
    return FacebookPostsImporter.main()


if __name__ == "__main__":
    exit(main())
