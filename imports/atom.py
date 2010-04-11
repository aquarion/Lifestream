#!/usr/bin/python

import feedparser, urlparse
import codecs, sys, os
import ConfigParser, MySQLdb, socket

sys.stdout = codecs.getwriter('utf8')(sys.stdout)

basedir = os.path.dirname(os.path.abspath(sys.argv[0]))

config = ConfigParser.ConfigParser()
config.readfp(open(basedir+'/../dbconfig.ini'))

db = {}

for item in config.items("database"):
	db[item[0]] = item[1]

dbcxn = MySQLdb.connect(user = db['username'], passwd = db['password'], db = db['database'], host = db['hostname'])
cursor = dbcxn.cursor()

if (len(sys.argv) < 2):
	print "Usage: rss Type url"
	sys.exit(5)

url = sys.argv[2]


fp = feedparser.parse(url)

#print '-- Welcome to Twipistula'

type = sys.argv[1]

s_sql = u'replace into lifestream (`type`, `systemid`, `title`, `url`, `date_created`) values (0, "%s", "%s", "%s", "%s", "%s");'

for i in range(len(fp['entries'])):
	o_item = fp['entries'][i]

	#id = kaboom[1]

	id = o_item['guid']

	#message = o_item.title.replace('"', '\\"');
	#if o_item.has_key("content"):
	#	message = o_item['content'][0]['value'].replace('"', '\\"');
	#else:
	#	message = o_item['title']+": "+o_item['description'].replace('"', '\\"');
	message = o_item['title'].replace('"', '\\"');
	cursor.execute(s_sql, (type, id, message, o_item['links'][0]['href'], o_item['published']))
