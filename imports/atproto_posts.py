#!/usr/bin/python
# -*- coding: utf-8 -*-
# Python
import sys
import configparser
import logging
import dateutil.parser
from pprint import pprint
import ipdb

from atproto import Client as atClient

from urllib.parse import urlparse

# Local
import lifestream
import simplejson as json

lifestream.arguments.add_argument(
    '--site',
    required=False,
    help='Site to choose from',
    default=False)

lifestream.arguments.add_argument(
    '--all',
    required=False,
    help='Fetch all toots?',
    default=False,
    action='store_true',
    dest='all_pages')

lifestream.arguments.add_argument('--max_pages', type=int,
        help='How many pages (overriden by --all)',
        default=1,
        required=False)

args = lifestream.arguments.parse_args()

if args.site:
    sites = args.site
else:
    sites = []
    for section in lifestream.config.sections():
        subsection = section.split(":")
        if subsection[0] == 'atproto':
            sites.append(subsection[1])

Lifestream = lifestream.Lifestream()

logger = logging.getLogger('AtProto')

for site in sites:
    source = site
    type = "atproto"
    try:
        # base_url = lifestream.config.get("atproto:%s" % source, "base_url")
        username = lifestream.config.get(
            "atproto:%s" % source, "username")
        password = lifestream.config.get(
            "atproto:%s" % source, "password")
        handle = lifestream.config.get(
            "atproto:%s" % source, "handle")
        server_base = lifestream.config.get(
            "atproto:%s" % source, "server_base", fallback=None)
    except configparser.NoSectionError:
        logger.error("No [atproto:%s] section found in config" % source)
        sys.exit(5)
    except configparser.NoOptionError as e:
        logger.error(e.message)
        sys.exit(5)

    if server_base:
        atserver = atClient(server_base)
    else:
        atserver = atClient() ## Default to bsky.app

    atserver.login(username, password)

    
    this_page = 0
    keep_going = True

    last_seen = False

    while keep_going:

        if last_seen:
            atResponse = atserver.get_author_feed(actor=handle, cursor=last_seen, limit=30)
        else:
            atResponse = atserver.get_author_feed(actor=handle, limit=30)

        last_seen = atResponse.cursor

        for item in atResponse.feed:
            if item.post.author.handle != handle:
                logger.debug("Skipping retweet from %s" % item.post.author.handle)
                continue

            if item.post.record.reply:
                pprint(item.post.record.reply)
                logger.debug("Skipping reply to %s" % item.post.record.reply.parent.uri)
                continue
            
            post = item.post.record
            embed = item.post.embed
            
            title=post.text
            source=site
            date=dateutil.parser.isoparse(post.created_at)
            
            at_url = urlparse(item.post.uri)
            post_id = at_url.path.split("/")[2]

            url = "https://{}/profile/{}/post/{}".format(site, handle, post_id)


            if embed and embed['py_type'] == "app.bsky.embed.images#viewImage":
                for media in embed.images:
                    if media['py_type'] == "app.bsky.embed.images#viewImage":
                        thumbnail = media['thumb']
                        break
            else:
                thumbnail = ''

            Lifestream.add_entry(
                id=item.post.uri,
                title=title,
                source=source,
                date=date,
                url=url,
                image=thumbnail,
                fulldata_json=item.post.model_dump_json(),
                type=type
            )

            logger.info("%s: %s" % (date.strftime("%Y-%m-%d"), title))
            pprint(post)

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
