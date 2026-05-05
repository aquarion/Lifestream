# -*- coding: utf-8 -*-
# Python
import configparser
import logging
import sys

import mastodon as mastodonpy

# Local
import lifestream
from lifestream.db import EntryStore

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
        if section[0:9] == "mastodon:":
            sites.append(section[9:])

entry_store = EntryStore()

logger = logging.getLogger("Mastodon")


def _get_thumbnail(toot):
    for media in toot["media_attachments"]:
        if media["type"] == "image":
            return media["url"]
    return ""


def _connect(site):
    try:
        base_url = lifestream.config.get("mastodon:%s" % site, "base_url")
        client_key = lifestream.config.get("mastodon:%s" % site, "client_key")
        client_secret = lifestream.config.get("mastodon:%s" % site, "client_secret")
        access_token = lifestream.config.get("mastodon:%s" % site, "access_token")
    except configparser.NoSectionError:
        logger.error("No [mastodon:%s] section found in config" % site)
        sys.exit(5)
    except configparser.NoOptionError as e:
        logger.error(str(e))
        sys.exit(5)
    return mastodonpy.Mastodon(
        client_id=client_key,
        client_secret=client_secret,
        api_base_url=base_url,
        access_token=access_token,
    )


def process_site(site):
    mastodon = _connect(site)

    if not mastodon.instance_health():
        logger.error("{} is not fine".format(site))
        sys.exit(5)

    me = mastodon.me()
    this_page = 0
    keep_going = True
    last_seen = False

    while keep_going:
        if last_seen:
            toots = mastodon.account_statuses(me["id"], min_id=last_seen)
        else:
            toots = mastodon.account_statuses(me["id"])

        for toot in toots:
            entry_store.add_entry(
                id=toot["id"],
                title=toot["content"],
                source=site,
                date=toot["created_at"],
                url=toot["url"],
                image=_get_thumbnail(toot),
                fulldata_json=lifestream.force_json(toot),
                type="mastodon",
            )

        if not len(toots):
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
