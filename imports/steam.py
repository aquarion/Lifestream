#!/usr/bin/python

import lifestream
from xml.dom import minidom
import urllib
import hashlib
import sys
import time
DEBUG = False;


dbcxn  = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)


type = "steam"

if (len(sys.argv) < 2):
        print "Usage: %s username" % sys.argv[0]
        sys.exit(5)

user = sys.argv[1]

s_sql = u'insert delayed ignore into lifestream (`id`, `type`, `systemid`, `title`, `date_created`, `image`, `url`, `source`) values (0, %s, %s, %s, NOW(), %s, %s, "steam");'

if DEBUG:
	print "Opening http://steamcommunity.com/id/%s/games?tab=recent&xml=1" % user;

try:
	gameslist_xml = urllib.urlopen("http://steamcommunity.com/id/%s/games?tab=recent&xml=1" % user)
except IOError:
	print >> sys.stderr, "Got socket error fetching games list"
	os._exit(5)

games = minidom.parse(gameslist_xml);

gamesList = games.getElementsByTagName('game')

maxGames   = 10
thisGame   = 0
foundGames = 0

#for game in gameslist:
while (foundGames < maxGames and thisGame != len(gamesList)):

	# Get the current game
	game = gamesList[thisGame]
	
	# Iterate Loop counter to get the next game next time
	thisGame = thisGame + 1;

	statspage = game.getElementsByTagName('statsLink')
	gamename = game.getElementsByTagName('name')[0].firstChild.data
	
	if DEBUG:
		print "% 3d % 3d %s" % (foundGames, thisGame, gamename)
	
	if len(statspage) == 0:
		if DEBUG:
			print "       + Skipping %s" % gamename	
		continue;
	else:
		if DEBUG:
			print "       + Keeping %s" % gamename	

	# If we found a statspage, carry on. Iterate foundGames	

	foundGames = foundGames + 1;


	statspage = game.getElementsByTagName('statsLink')[0].firstChild.data
	statspagexml = "%s?xml=1" % statspage

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

		if DEBUG:
			print "         %s" % name	

		message = "%s &ndash; %s" % (gamename, name)
	
		m.update(gamename);
		m.update(name); 
		id = image
	
		#print "   %s %s " % (name, image)
	
		#print s_sql % (type, id, message, image, statspage)
		cursor.execute(s_sql, (type, id, message, image, statspage))

	time.sleep(5)
