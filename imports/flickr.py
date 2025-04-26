#!/usr/bin/python

# Python
import logging
import sys

# Libraries
import flickrapi

# Local
import lifestream

logging.root.handlers.pop(0)  # remove Flickrapi's log handler

max_pages = False
per_page = 100

API_KEY = lifestream.config.get("flickr", "api_key")
API_SECRET = lifestream.config.get("flickr", "api_secret")
FLICKRID = lifestream.config.get("flickr", "account")
FLICKRNAME = lifestream.config.get("flickr", "account_name")

DEBUG = False
dbcxn = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)


Lifestream = lifestream.Lifestream()

logger = logging.getLogger("Flickr")
args = lifestream.arguments.parse_args()

# Only search from the most recent result
sql = 'select date_created from lifestream where type = "flickr" order by date_created desc limit 1 '
cursor.execute(sql)
res = cursor.fetchone()

if res:
    since = res[0]
else:
    since = 0

flickr = flickrapi.FlickrAPI(API_KEY)
photos_xml = flickr.photos_search(
    user_id=FLICKRID, per_page=per_page, page=1, min_taken_date=since
)
# sets = flickr.photosets_getList(user_id='73509078@N00')


pages = int(photos_xml.find("photos").attrib["pages"])

logger.info("Since %s" % since)

if pages == 0:
    logger.info("Nothing found")
    sys.exit(0)

if max_pages and pages > max_pages:
    pages = max_pages


# % (farm, server, id, secret, size)
s_url = "http://farm%s.staticflickr.com/%s/%s_%s_%s.jpg"

size_code = "z"
type = "flickr"


for page in range(1, pages + 1):
    logger.info("Page %d of %d" % (page, pages))
    photos_xml = flickr.photos_search(
        user_id=FLICKRID, per_page=per_page, page=page, min_taken_date=since
    )
    photos = photos_xml.find("photos").findall("photo")
    for photo in photos:
        image = s_url % (
            photo.attrib["farm"],
            photo.attrib["server"],
            photo.attrib["id"],
            photo.attrib["secret"],
            size_code,
        )

        info = flickr.photos_getinfo(
            photo_id=photo.attrib["id"], secret=photo.attrib["secret"]
        )

        page_url = info.find("photo").find("urls").find("url").text
        title = info.find("photo").find("title").text
        id = photo.attrib["id"]
        date_taken = info.find("photo").find("dates").attrib["taken"]

        logger.info("     %s %s" % (date_taken, title))

        Lifestream.add_entry(
            type="flickr",
            id=id,
            title=title,
            url=page_url,
            source="flickr",
            date=date_taken,
            image=image,
        )

dbcxn.close()
