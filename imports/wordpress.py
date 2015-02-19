#!/usr/bin/python
# -*- coding: utf-8 -*-

import lifestream

import feedparser
import sys
import codecs, locale
from datetime import datetime
from time import mktime

import argparse, ConfigParser
print sys.stdout.encoding

from wordpress_xmlrpc import Client, WordPressPost
from wordpress_xmlrpc.methods.posts import GetPosts, NewPost
from wordpress_xmlrpc.methods.users import GetUserInfo

parser = argparse.ArgumentParser(description='Process some integers.')
parser.add_argument('site', type=str,
                   help='Site, as defined in config.ini')
parser.add_argument('--all', action="store_true",
                   help='Fetch all posts?',
                   dest='all_pages')
parser.add_argument('--max_pages', type=int, 
                   help='How many pages to fix (overriden by --all)',
                   default=1,
                   required=False)

args = parser.parse_args()

source = args.site
type = "wordpress"

Lifestream = lifestream.Lifestream()

try:
    url    = lifestream.config.get("wordpress:%s" % source, "url")
    user   = lifestream.config.get("wordpress:%s" % source, "username")
    passwd = lifestream.config.get("wordpress:%s" % source, "password")
except ConfigParser.NoSectionError:
    print "No [wordpress:%s] section found in config" % source
    sys.exit(5)
except ConfigParser.NoOptionError as e:
    print e.message
    sys.exit(5)


wp = Client(url, user, passwd)

this_page = 0
keep_going = True

while keep_going:
    options = {
        'number' : 30,
        'offset' : this_page * 30,
        'post_status' : 'publish'
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

        print "%s: %s" % (post.date.strftime("%Y-%m-%d"), title)

    if not len(posts):
        keep_going = False

    this_page += 1
    if this_page >= args.max_pages and not args.all_pages:
        keep_going = False
    elif not args.all_pages:
        print "Page %d of max %d" % (this_page, args.max_pages)
    else:
        print "Next Page..."


# import ipdb
# ipdb.set_trace()

# for i in range(len(fp['entries'])):
#     o_item = fp['entries'][i]
#     id = o_item['guid']
#     dt = datetime.fromtimestamp(mktime(o_item['updated_parsed']))
#     updated = dt.strftime("%Y-%m-%d %H:%M")

#     Lifestream.add_entry(
#         type=type,
#         id=id,
#         title=o_item['title'],
#         source=type,
#         date=updated,
#         url=o_item['links'][0]['href'])
