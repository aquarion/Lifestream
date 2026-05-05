# -*- coding: utf-8 -*-
# Python
import configparser
import logging

# Libraries
from wordpress_xmlrpc import Client
from wordpress_xmlrpc import exceptions as wordpress_exceptions
from wordpress_xmlrpc.methods.posts import GetPosts

# Local
import lifestream
from lifestream.db import EntryStore

lifestream.arguments.add_argument(
    "site", type=str, help="Site, as defined in config.ini", nargs="*"
)
lifestream.arguments.add_argument(
    "--all", action="store_true", help="Fetch all posts?", dest="all_pages"
)
lifestream.arguments.add_argument(
    "--max_pages",
    type=int,
    help="How many pages (overriden by --all)",
    default=1,
    required=False,
)
args = lifestream.parse_args()

if args.site:
    sites = args.site
else:
    sites = []
    for section in lifestream.config.sections():
        if section[0:10] == "wordpress:":
            sites.append(section[10:])

entry_store = EntryStore()

logger = logging.getLogger("Wordpress")


def _post_title(post):
    if len(post.title):
        return post.title
    if post.excerpt:
        return post.excerpt
    return "[Untitled Post]"


def _connect(site):
    try:
        url = lifestream.config.get("wordpress:%s" % site, "url")
        user = lifestream.config.get("wordpress:%s" % site, "username")
        passwd = lifestream.config.get("wordpress:%s" % site, "password")
    except configparser.NoSectionError:
        logger.error("No [wordpress:%s] section found in config" % site)
        return None
    except configparser.NoOptionError as e:
        logger.error(e.message)
        return None
    return Client(url, user, passwd)


def process_site(site):
    logger.info(site)
    wp = _connect(site)
    if not wp:
        return
    this_page = 0
    keep_going = True

    while keep_going:
        options = {"number": 30, "offset": this_page * 30, "post_status": "publish"}
        try:
            posts = wp.call(GetPosts(options))
        except wordpress_exceptions.InvalidCredentialsError as e:
            logger.error("Invalid credentials for %s: %s" % (site, str(e)))
            break

        for post in posts:
            thumbnail = (
                post.thumbnail["link"]
                if post.thumbnail and "link" in post.thumbnail
                else ""
            )
            entry_store.add_entry(
                id=post.guid,
                title=_post_title(post),
                source=site,
                date=post.date.strftime("%Y-%m-%d %H:%M"),
                url=post.link,
                image=thumbnail,
                type="wordpress",
            )
            logger.info("%s: %s" % (post.date.strftime("%Y-%m-%d"), _post_title(post)))

        if not len(posts):
            keep_going = False

        this_page += 1
        if this_page >= args.max_pages and not args.all_pages:
            keep_going = False
        elif not args.all_pages:
            logger.info("Page %d of max %d" % (this_page, args.max_pages))
        else:
            logger.info("Next Page...")


for site in sites:
    process_site(site)
