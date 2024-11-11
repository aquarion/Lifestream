#!/usr/bin/python
# -*- coding: utf-8 -*-
# Python
import sys
import configparser
import logging
from pprint import pprint

import mastodon as mastodonpy

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
        if section[0:9] == 'mastodon:':
            sites.append(section[9:])

Lifestream = lifestream.Lifestream()

logger = logging.getLogger('Mastodon')

for site in sites:
    source = site
    type = "mastodon"
    try:
        base_url = lifestream.config.get("mastodon:%s" % source, "base_url")
        client_key = lifestream.config.get(
            "mastodon:%s" % source, "client_key")
        client_secret = lifestream.config.get(
            "mastodon:%s" % source, "client_secret")
        access_token = lifestream.config.get(
            "mastodon:%s" % source, "access_token")
    except configparser.NoSectionError:
        logger.error("No [mastodon:%s] section found in config" % source)
        sys.exit(5)
    except configparser.NoOptionError as e:
        logger.error(e.message)
        sys.exit(5)

    mastodon = mastodonpy.Mastodon(
        client_id=client_key,
        client_secret=client_secret,
        api_base_url=base_url,
        access_token=access_token
    )

    this_page = 0
    keep_going = True

    how_are_you = mastodon.instance_health()

    if not how_are_you:
        logger.error("{} is not fine".format(site))
        sys.exit(5)

    me = mastodon.me()

    last_seen = False

    while keep_going:

        if last_seen:
            toots = mastodon.account_statuses(me['id'], min_id=last_seen)
        else:
            toots = mastodon.account_statuses(me['id'])

        for toot in toots:
            title = toot['content']

            if len(toot['media_attachments']):
                for media in toot['media_attachments']:
                    if media['type'] == "image":
                        thumbnail = media['url']
                        break
            else:
                thumbnail = ''

            Lifestream.add_entry(
                id=toot['id'],
                title=title,
                source=source,
                date=toot['created_at'],
                url=toot['url'],
                image=thumbnail,
                fulldata_json=lifestream.force_json(toot),
                type=type
            )

        #     logger.info("%s: %s" % (post.date.strftime("%Y-%m-%d"), title))

        if not len(toots):
            keep_going = False

        this_page += 1
        if this_page >= args.max_pages and not args.all_pages:
            keep_going = False
        elif not args.all_pages:
            logger.info("Page %d of max %d" % (this_page, args.max_pages))
        else:
            logger.info("Next Page...")
