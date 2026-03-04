"""Flickr photo importer for Lifestream."""

import logging

import flickrapi

from lifestream.core.db import get_connection, get_cursor
from lifestream.importers.base import BaseImporter


class FlickrImporter(BaseImporter):
    """Import photos from Flickr."""

    name = "flickr"
    description = "Import photos from Flickr"
    config_section = "flickr"

    # Static URL template: farm, server, id, secret, size
    STATIC_URL_TEMPLATE = "http://farm%s.staticflickr.com/%s/%s_%s_%s.jpg"
    MAX_PAGES = False
    PER_PAGE = 100
    SIZE_CODE = "z"

    def __init__(self):
        """Initialize and remove flickrapi's log handler."""
        super().__init__()
        # Remove Flickrapi's log handler if present
        if logging.root.handlers:
            for handler in logging.root.handlers[:]:
                if (
                    hasattr(handler, "__module__")
                    and "flickr" in str(handler.__module__).lower()
                ):
                    logging.root.removeHandler(handler)

    def validate_config(self) -> bool:
        """Ensure Flickr credentials are configured."""
        if not self.get_config("api_key"):
            self.logger.error("No Flickr api_key in config")
            return False
        if not self.get_config("account"):
            self.logger.error("No Flickr account in config")
            return False
        return True

    def run(self) -> None:
        """Import photos from Flickr."""
        api_key = self.get_config("api_key")
        flickr_id = self.get_config("account")

        dbcxn = get_connection()
        cursor = get_cursor(dbcxn)

        # Only search from the most recent result
        sql = 'select date_created from lifestream where type = "flickr" order by date_created desc limit 1'
        cursor.execute(sql)
        res = cursor.fetchone()
        since = res[0] if res else 0

        flickr = flickrapi.FlickrAPI(api_key)
        photos_xml = flickr.photos_search(
            user_id=flickr_id, per_page=self.PER_PAGE, page=1, min_taken_date=since
        )

        pages = int(photos_xml.find("photos").attrib["pages"])
        self.logger.info("Since %s", since)

        if pages == 0:
            self.logger.info("Nothing found")
            dbcxn.close()
            return

        if self.MAX_PAGES and pages > self.MAX_PAGES:
            pages = self.MAX_PAGES

        for page in range(1, pages + 1):
            self.logger.info("Page %d of %d", page, pages)
            photos_xml = flickr.photos_search(
                user_id=flickr_id,
                per_page=self.PER_PAGE,
                page=page,
                min_taken_date=since,
            )
            photos = photos_xml.find("photos").findall("photo")

            for photo in photos:
                image = self.STATIC_URL_TEMPLATE % (
                    photo.attrib["farm"],
                    photo.attrib["server"],
                    photo.attrib["id"],
                    photo.attrib["secret"],
                    self.SIZE_CODE,
                )

                info = flickr.photos_getinfo(
                    photo_id=photo.attrib["id"], secret=photo.attrib["secret"]
                )

                page_url = info.find("photo").find("urls").find("url").text
                title = info.find("photo").find("title").text
                photo_id = photo.attrib["id"]
                date_taken = info.find("photo").find("dates").attrib["taken"]

                self.logger.info("     %s %s", date_taken, title)

                self.entry_store.add_entry(
                    type="flickr",
                    id=photo_id,
                    title=title,
                    url=page_url,
                    source="flickr",
                    date=date_taken,
                    image=image,
                )

        dbcxn.close()


def main():
    """Entry point for CLI."""
    return FlickrImporter.main()


if __name__ == "__main__":
    exit(main())
