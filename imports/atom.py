#!/usr/bin/python

# Python
import logging
from datetime import datetime
from time import mktime
# Libraries
import feedparser
# Local
import lifestream


logger = logging.getLogger('Atom')

lifestream.arguments.add_argument('type')
lifestream.arguments.add_argument('url')

args = lifestream.arguments.parse_args()

Lifestream = lifestream.Lifestream()

logger.info('Grabbing %s' % args.url)
fp = feedparser.parse(args.url)

for i in range(len(fp['entries'])):
    o_item = fp['entries'][i]
    id = o_item['guid']
    dt = datetime.fromtimestamp(mktime(o_item['updated_parsed']))
    updated = dt.strftime("%Y-%m-%d %H:%M")
    logger.info("Adding new %s item: %s" % (args.type, o_item['title']))

    Lifestream.add_entry(
        type=args.type,
        id=id,
        title=o_item['title'],
        source=args.type,
        date=updated,
        url=o_item['links'][0]['href'])
