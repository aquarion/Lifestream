"""WordPress posts importer for Lifestream."""

import argparse
import configparser

from wordpress_xmlrpc import Client
from wordpress_xmlrpc import exceptions as wordpress_exceptions
from wordpress_xmlrpc.methods.posts import GetPosts

from lifestream.importers.base import BaseImporter
from lifestream.core import config


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

    def process_site(self, site: str) -> None:  # noqa: C901
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
            self.logger.error(f"No [{section}] section found in config")
            return
        except configparser.NoOptionError as e:
            self.logger.error(str(e))
            return

        wp = Client(url, user, passwd)

        this_page = 0
        keep_going = True

        while keep_going:
            options = {"number": 30, "offset": this_page * 30, "post_status": "publish"}
            try:
                posts = wp.call(GetPosts(options))
            except wordpress_exceptions.InvalidCredentialsError as e:
                self.logger.error(f"Invalid credentials for {source}: {e}")
                keep_going = False
                continue

            for post in posts:
                if len(post.title):
                    title = post.title
                elif post.excerpt:
                    title = post.excerpt
                else:
                    title = "[Untitled Post]"

                if post.thumbnail and "link" in post.thumbnail:
                    thumbnail = post.thumbnail["link"]
                else:
                    thumbnail = ""

                self.entry_store.add_entry(
                    id=post.guid,
                    title=title,
                    source=source,
                    date=post.date.strftime("%Y-%m-%d %H:%M"),
                    url=post.link,
                    image=thumbnail,
                    type=entry_type,
                )

                self.logger.info(f"{post.date.strftime('%Y-%m-%d')}: {title}")

            if not len(posts):
                keep_going = False

            this_page += 1
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
            self.logger.error("No WordPress sites configured")
            return

        for site in sites:
            self.process_site(site)


def main():
    """Entry point for CLI."""
    return WordpressImporter.main()


if __name__ == "__main__":
    exit(main())
