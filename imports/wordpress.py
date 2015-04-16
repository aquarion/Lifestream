#!/usr/bin/python
# -*- coding: utf-8 -*-
# Python
import sys
import codecs
import locale
from datetime import datetime
from time import mktime
import argparse
import ConfigParser
import logging

# Libraries
from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import GetPosts, NewPost
from wordpress_xmlrpc.methods.users import GetUserInfo

# Local
import lifestream

lifestream.arguments.add_argument('site', type=str,
                                  help='Site, as defined in config.ini',
                                  nargs='*')
lifestream.arguments.add_argument('--all', action="store_true",
                                  help='Fetch all posts?',
                                  dest='all_pages')
lifestream.arguments.add_argument('--max_pages', type=int,
                                  help='How many pages (overriden by --all)',
                                  default=1,
                                  required=False)

args = lifestream.arguments.parse_args()

if args.site:
    sites = [args.site, ]
else:
    sites = []
    for section in lifestream.config.sections():
        if section[0:10] == 'wordpress:':
            sites.append(section[10:])

Lifestream = lifestream.Lifestream()

logger = logging.getLogger('Wordpress')


for site in sites:
    source = site
    type = "wordpress"
    logger.info(site)
    try:
        url = lifestream.config.get("wordpress:%s" % source, "url")
        user = lifestream.config.get("wordpress:%s" % source, "username")
        passwd = lifestream.config.get("wordpress:%s" % source, "password")
    except ConfigParser.NoSectionError:
        logger.error("No [wordpress:%s] section found in config" % source)
        sys.exit(5)
    except ConfigParser.NoOptionError as e:
        logger.error(e.message)
        sys.exit(5)

    wp = Client(url, user, passwd)

    this_page = 0
    keep_going = True

    while keep_going:
        options = {
            'number': 30,
            'offset': this_page * 30,
            'post_status': 'publish'
        }
        posts = wp.call(GetPosts(options))
        for post in posts:
            if len(post.title):
                title = post.title
            elif post.excerpt:
                title = post.excerpt
            else:
                title = "[Untitled Post]"

            if post.thumbnail and 'link' in post.thumbnail:
                thumbnail = post.thumbnail['link']
            else:
                thumbnail = ''

            Lifestream.add_entry(
                id=post.guid,
                title=title,
                source=source,
                date=post.date.strftime("%Y-%m-%d %H:%M"),
                url=post.link,
                image=thumbnail,
                # fulldata_json=post.struct,
                type=type)

            logger.info("%s: %s" % (post.date.strftime("%Y-%m-%d"), title))

        if not len(posts):
            keep_going = False

        this_page += 1
        if this_page >= args.max_pages and not args.all_pages:
            keep_going = False
        elif not args.all_pages:
            logger.info("Page %d of max %d" % (this_page, args.max_pages))
        else:
            logger.info("Next Page...")
