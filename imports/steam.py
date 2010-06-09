#!/usr/bin/python
from xml.dom import minidom
import urllib
import hashlib
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

type = "steam"

if (len(sys.argv) < 2):
        print "Usage: %s username" % sys.argv[0]
        sys.exit(5)

user = sys.argv[1]

s_sql = u'insert ignore into lifestream (`id`, `type`, `systemid`, `title`, `date_created`, `image`, `url`, `source`) values (0, %s, %s, %s, NOW(), %s, %s, "steam");'

try:
	gameslist_xml = urllib.urlopen("http://steamcommunity.com/id/%s/games?tab=recent&xml=1" % user)
except IOError:
	print >> sys.stderr, "Got socket error fetching games list"
	os._exit(5)

games = minidom.parse(gameslist_xml);
gameslist = games.getElementsByTagName('game')
for game in gameslist[0:3]:
	statspage = game.getElementsByTagName('statsLink')
	gamename = game.getElementsByTagName('name')[0].firstChild.data
	#print gamename
	if len(statspage) == 0:
		continue;

	statspage = game.getElementsByTagName('statsLink')[0].firstChild.data
	statspagexml = "%s?xml=1" % statspage
	#print "%s %s" % (gamename, statspage)

	try:
		game = minidom.parse(urllib.urlopen(statspagexml))
	except IOError:
		print >> sys.stderr, "Got socket error fetching %s achievement list" % gamename
		os._exit(5)

	for achivement in game.getElementsByTagName("achievement"):
		closed =  achivement.getAttribute("closed")
		if closed == u'0':
				continue
	
		m = hashlib.md5()
		
		name = achivement.getElementsByTagName('name')[0].firstChild.data
		image = achivement.getElementsByTagName('iconClosed')[0].firstChild.data
	
		message = "%s &ndash; %s" % (gamename, name)
	
		m.update(gamename);
		m.update(name); 
		id = image
	
		#print "   %s %s " % (name, image)
	
		#print s_sql % (type, id, message, image, statspage)
		cursor.execute(s_sql, (type, id, message, image, statspage))

	time.sleep(5)
