#!/usr/bin/python
from xml.dom import minidom
import urllib
import hashlib

type = "steam"

s_sql = u'insert ignore into lifestream (`id`, `type`, `systemid`, `title`, `date_created`, `image`, `url`) values (0, "%s", "%s", "%s", NOW(), "%s", "%s");'

games = minidom.parse(urllib.urlopen("http://steamcommunity.com/id/aquarion/games?xml=1"));
gameslist = games.getElementsByTagName('game')
for game in gameslist:
	statspage = game.getElementsByTagName('statsLink')
	if len(statspage) == 0:
		continue;

	gamename = game.getElementsByTagName('name')[0].firstChild.data
	statspage = game.getElementsByTagName('statsLink')[0].firstChild.data
	statspagexml = "%s?xml=1" % statspage
	#print "%s %s" % (gamename, statspage)


	game = minidom.parse(urllib.urlopen(statspagexml))

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
	
		print s_sql % (type, id, message, image, statspage)
