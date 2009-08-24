#!/usr/bin/python

import feedparser, urlparse
import codecs, sys
sys.stdout = codecs.getwriter('utf8')(sys.stdout)


if (len(sys.argv) < 2):
	print "Usage: steam steamid"
	sys.exit(5)

id = sys.argv[1]

url = "http://pipes.yahoo.com/pipes/pipe.run?_id=71f8cecd10ee3c70ebcfadd808335e76&_render=rss&steamid=%s" % id

fp = feedparser.parse(url)

#print '-- Welcome to Twipistula'

type = "steam"

s_sql = u'insert ignore into lifestream (`id`, `type`, `systemid`, `title`, `date_created`, `image`, `url`) values (0, "%s", "%s", "%s", NOW(), "%s", "%s");'

for i in range(len(fp['entries'])):
	o_item = fp['entries'][i]

	#id = kaboom[1]

	id = o_item['guid']

	#message = o_item.title.replace('"', '\\"');
	if o_item.has_key("content"):
		message = o_item['content'][0]['value'].replace('"', '\\"');
	else:
		message = o_item['title']+": "+o_item['description'].replace('"', '\\"');

	image = o_item['media_content'][0]['url']
	link = o_item['link']

	#print o_item
	#sys.exit(5)
	print s_sql % (type, id, message, image, link)
