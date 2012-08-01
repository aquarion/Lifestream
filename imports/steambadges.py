#!/usr/bin/python

import lifestream
import sys
from BeautifulSoup import BeautifulSoup
import pytz

import hashlib

from datetime import datetime

from mechanize import Browser, RobustFactory

from time import sleep

from datetime import datetime

dbcxn  = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)


if (len(sys.argv) < 2):
	print "Usage: %s username " % sys.argv[0]
	sys.exit(5)

USERNAME     = sys.argv[1]

utctime    = pytz.utc
steamtime     = pytz.timezone('US/Pacific')

br = br = Browser(factory=RobustFactory())
br.set_handle_robots(False)

################ Login

URL = "http://steamcommunity.com/id/%s/badges?xml=1" % USERNAME

response = br.open(URL)

html = br.response().read();

s_sql = u'INSERT IGNORE INTO lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`, `image`) values (%s, %s, %s, %s, %s, %s, %s);'

soup = BeautifulSoup(html)

badges = soup.findAll("div", {"class":"badge"})

for badge in badges:
	src = badge.findAll("div", {"class" : "badge_logo"} )[0].findAll("img")[0].attrs[0][1]
	name = badge.findAll("div", {"class" : "badge_name"} )[0].string
	desc = badge.findAll("div", {"class" : "badge_description"} )[0].string
	date = badge.findAll("div", {"class" : "badge_unlocked"} )[0].string[10:]
	
	text = "%s &mdash; %s" % (name, desc)
	
	parseddate = datetime.strptime(date, "%b %d, %Y %I:%M%p")
	localdate  = steamtime.localize(parseddate)
	utcdate    = localdate.astimezone(utc)
	
	id = hashlib.md5()
	id.update(text)
	
	cursor.execute(s_sql, ("gaming", id.hexdigest(), text, utcdate, URL, "steambadge", src))
	
	
