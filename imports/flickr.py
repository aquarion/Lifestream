#!/usr/bin/python

import feedparser, urlparse
import os, time,sys,codecs
import ConfigParser, MySQLdb, socket
sys.stdout = codecs.getwriter('utf8')(sys.stdout)
import dateutil.parser

basedir = os.path.dirname(os.path.abspath(sys.argv[0]))

config = ConfigParser.ConfigParser()
config.readfp(open(basedir+'/../dbconfig.ini'))

db = {}

for item in config.items("database"):
	db[item[0]] = item[1]

dbcxn = MySQLdb.connect(user = db['username'], passwd = db['password'], db = db['database'], host = db['hostname'])
cursor = dbcxn.cursor()


if (len(sys.argv) < 3):
	print "Usage: flickr type ID"
	sys.exit(5)

url = "http://api.flickr.com/services/feeds/photos_public.gne?id=%s&lang=en-us&format=atom" % sys.argv[2]


fp = feedparser.parse(url)

#print '-- Welcome to Twipistula'

type = sys.argv[1]

s_sql = u'replace into lifestream (`type`, `systemid`, `title`, `url`, `date_created`, `source`, `image`) values (%s, %s, %s, %s, %s, "", "");'

for i in range(len(fp['entries'])):
	o_item = fp['entries'][i]

	#id = kaboom[1]

	id = o_item['guid']

	result = dateutil.parser.parse( o_item['published'])

	#message = o_item.title.replace('"', '\\"');
	#if o_item.has_key("content"):
	#	message = o_item['content'][0]['value'].replace('"', '\\"');
	#else:
	#	message = o_item['title']+": "+o_item['description'].replace('"', '\\"');
	message = o_item['title'].replace('"', '\\"');
	#print s_sql % (type, id, message, o_item['links'][0]['href'], o_item['published'])
	cursor.execute(s_sql, (type, id, message, o_item['links'][0]['href'],  result))
