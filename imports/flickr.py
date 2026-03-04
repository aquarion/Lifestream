#!/usr/bin/python
"""Flickr photo importer for Lifestream."""

# Python
import logging
import sys

# Libraries
import flickrapi

# Local
import lifestream
from lifestream.db import EntryStore
from lifestream.db import get_connection, get_cursor

# Remove Flickrapi's log handler
logging.root.handlers.pop(0)

logger = logging.getLogger("Flickr")

# Static URL template: farm, server, id, secret, size
STATIC_URL_TEMPLATE = "http://farm%s.staticflickr.com/%s/%s_%s_%s.jpg"
MAX_PAGES = False
PER_PAGE = 100
SIZE_CODE = "z"


def main():
    """Import photos from Flickr."""
    args = lifestream.parse_args()

    api_key = lifestream.config.get("flickr", "api_key")
    flickr_id = lifestream.config.get("flickr", "account")

    dbcxn = get_connection()
    cursor = get_cursor(dbcxn)
    entry_store = EntryStore()

    # Only search from the most recent result
    sql = 'select date_created from lifestream where type = "flickr" order by date_created desc limit 1'
    cursor.execute(sql)
    res = cursor.fetchone()
    since = res[0] if res else 0

    flickr = flickrapi.FlickrAPI(api_key)
    photos_xml = flickr.photos_search(
        user_id=flickr_id, per_page=PER_PAGE, page=1, min_taken_date=since
    )

    pages = int(photos_xml.find("photos").attrib["pages"])
    logger.info("Since %s", since)

    if pages == 0:
        logger.info("Nothing found")
        dbcxn.close()
        sys.exit(0)

    if MAX_PAGES and pages > MAX_PAGES:
        pages = MAX_PAGES

    for page in range(1, pages + 1):
        logger.info("Page %d of %d", page, pages)
        photos_xml = flickr.photos_search(
            user_id=flickr_id, per_page=PER_PAGE, page=page, min_taken_date=since
        )
        photos = photos_xml.find("photos").findall("photo")
        for photo in photos:
            image = STATIC_URL_TEMPLATE % (
                photo.attrib["farm"],
                photo.attrib["server"],
                photo.attrib["id"],
                photo.attrib["secret"],
                SIZE_CODE,
            )

            info = flickr.photos_getinfo(
                photo_id=photo.attrib["id"], secret=photo.attrib["secret"]
            )

            page_url = info.find("photo").find("urls").find("url").text
            title = info.find("photo").find("title").text
            photo_id = photo.attrib["id"]
            date_taken = info.find("photo").find("dates").attrib["taken"]

            logger.info("     %s %s", date_taken, title)

            entry_store.add_entry(
                type="flickr",
                id=photo_id,
                title=title,
                url=page_url,
                source="flickr",
                date=date_taken,
                image=image,
            )

    dbcxn.close()


if __name__ == "__main__":
    main()
