#!/usr/bin/python

import lifestream
import sys
from BeautifulSoup import BeautifulSoup
import hashlib

from mechanize import Browser, RobustFactory

from datetime import datetime

dbcxn  = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)

if (len(sys.argv) < 2):
	print "Usage: %s charactername[,charactername] " % sys.argv[0]
	sys.exit(5)

CHARACTERS     = sys.argv[1]

br = br = Browser(factory=RobustFactory())
br.set_handle_robots(False)

################ Login

for character in CHARACTERS.split(","):

	url = "http://chronicle.thesecretworld.com/character/%s" % character

	response = br.open(url)

	html = br.response().read();

	s_sql = u'INSERT IGNORE INTO lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`, `image`) values (%s, %s, %s, NOW(), %s, %s, %s);'

	soup = BeautifulSoup(html)

	rank = soup.findAll("div", {"class":"x6"})

	rank = rank[0]

	img = rank.findAll("img")[0]

	src = img.attrs[0][1]

	rank_n = rank.findAll("div", {"class":"rank wf"})[0]
	rank_t = rank.findAll("div", {"class":"title wf"})[0]

	text = "%s achieved %s&ndash;%s" % (character, rank_n.string, rank_t.string)

	id = hashlib.md5()
	id.update(text)
	cursor.execute(s_sql, ("gaming", id.hexdigest(), text, url, "The Secret World", src))
