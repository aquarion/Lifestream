#!/usr/bin/python

import lifestream
import sys
from BeautifulSoup import BeautifulSoup
import pytz
import re
import hashlib
import csv
import StringIO

from mechanize import Browser, RobustFactory

from time import sleep

from datetime import datetime

dbcxn  = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)


if (len(sys.argv) < 2):
	print "Usage: %s charactername " % sys.argv[0]
	sys.exit(5)

CHARACTER     = sys.argv[1]

londontime    = pytz.timezone("Europe/London")

br = br = Browser(factory=RobustFactory())
br.set_handle_robots(False)

################ Login

URL = "http://chronicle.thesecretworld.com/character/%s" % CHARACTER

response = br.open(URL)

html = br.response().read();

s_sql = u'INSERT IGNORE INTO lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`, `image`) values (%s, %s, %s, NOW(), %s, %s, %s);'

soup = BeautifulSoup(html)

rank = soup.findAll("div", {"class":"x6"})

rank = rank[0]

img = rank.findAll("img")[0]

src = img.attrs[0][1]

rank_n = rank.findAll("div", {"class":"rank wf"})[0]
rank_t = rank.findAll("div", {"class":"title wf"})[0]

text = "%s achieved %s&ndash;%s" % (CHARACTER, rank_n.string, rank_t.string)

id = hashlib.md5()
id.update(text)

cursor.execute(s_sql, ("gaming", id.hexdigest(), text, URL, "thesecretworld", src))
