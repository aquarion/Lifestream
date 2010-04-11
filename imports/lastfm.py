#!/usr/bin/python

import feedparser, urlparse, datetime,time
import os, time,sys,codecs
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
	print "Usage: lastfm lastfmid"
	sys.exit(5)

id = sys.argv[1]

url = "http://ws.audioscrobbler.com/1.0/user/%s/recenttracks.rss" % id

fp = feedparser.parse(url)

#print '-- Welcome to Twipistula'

type = "lastfm"

s_sql = u'replace into lifestream (`id`, `type`, `systemid`, `title`, `date_created`, `url` ) values (0, %s, %s, %s, %s, %s);'

for i in range(len(fp['entries'])):
	o_item = fp['entries'][i]

	id = o_item['guid']
	
	title = o_item.title.encode("utf_8")

	#print o_item;

	updated = datetime.datetime.fromtimestamp(time.mktime(o_item.updated_parsed)).strftime("%Y-%m-%d %H:%M");

	#title = o_item.title.replace('"', '\\"')
	#message = o_item.title.replace('"', '\\"');
	#print s_sql % (type, id, o_item.title, updated, o_item['link'])
	cursor.execute(s_sql, (type, id, title, updated, o_item['link']))
