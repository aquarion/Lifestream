# -*- coding: utf-8 -*-
# Python
import configparser
import logging
import sys
from urllib.parse import urlparse

import dateutil.parser

# Local
import lifestream_legacy as lifestream
from atproto import Client as atClient
from lifestream_legacy.db import EntryStore

lifestream.arguments.add_argument(
    "--site", required=False, help="Site to choose from", default=False
)

lifestream.arguments.add_argument(
    "--all",
    required=False,
    help="Fetch all toots?",
    default=False,
    action="store_true",
    dest="all_pages",
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
        subsection = section.split(":")
        if subsection[0] == "atproto":
            sites.append(subsection[1])

entry_store = EntryStore()

logger = logging.getLogger("AtProto")


def _get_thumbnail(embed):
    if embed and embed["py_type"] == "app.bsky.embed.images#viewImage":
        for media in embed.images:
            if media["py_type"] == "app.bsky.embed.images#viewImage":
                return media["thumb"]
    return ""


def _process_post(item, site, handle):
    if item.post.author.handle != handle:
        logger.debug("Skipping retweet from %s" % item.post.author.handle)
        return
    if item.post.record.reply:
        logger.debug("Skipping reply to %s" % item.post.record.reply.parent.uri)
        return
    post = item.post.record
    date = dateutil.parser.isoparse(post.created_at)
    post_id = urlparse(item.post.uri).path.split("/")[2]
    url = "https://{}/profile/{}/post/{}".format(site, handle, post_id)
    entry_store.add_entry(
        id=item.post.uri,
        title=post.text,
        source=site,
        date=date,
        url=url,
        image=_get_thumbnail(item.post.embed),
        fulldata_json=item.post.model_dump_json(),
        type="atproto",
    )
    logger.info("%s: %s" % (date.strftime("%Y-%m-%d"), post.text))


def process_site(site):
    try:
        username = lifestream.config.get("atproto:%s" % site, "username")
        password = lifestream.config.get("atproto:%s" % site, "password")
        handle = lifestream.config.get("atproto:%s" % site, "handle")
        server_base = lifestream.config.get(
            "atproto:%s" % site, "server_base", fallback=None
        )
    except configparser.NoSectionError:
        logger.error("No [atproto:%s] section found in config" % site)
        sys.exit(5)
    except configparser.NoOptionError as e:
        logger.error(e.message)
        sys.exit(5)

    atserver = atClient(server_base) if server_base else atClient()
    atserver.login(username, password)

    this_page = 0
    keep_going = True
    last_seen = False

    while keep_going:
        if last_seen:
            atResponse = atserver.get_author_feed(
                actor=handle, cursor=last_seen, limit=30
            )
        else:
            atResponse = atserver.get_author_feed(actor=handle, limit=30)

        last_seen = atResponse.cursor

        for item in atResponse.feed:
            _process_post(item, site, handle)

        if not len(atResponse.feed):
            logger.info("No more posts")
            keep_going = False

        this_page += 1
        if this_page >= args.max_pages and not args.all_pages:
            keep_going = False
            logger.info("Max pages ({}) reached".format(args.max_pages))
        elif not args.all_pages:
            logger.info("Page %d of max %d" % (this_page, args.max_pages))
        else:
            logger.info("Next Page...")


for site in sites:
    process_site(site)
