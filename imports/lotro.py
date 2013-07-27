#!/usr/bin/python

import lifestream
import hashlib

from BeautifulSoup import BeautifulSoup
from mechanize import Browser, RobustFactory

from datetime import datetime

dbcxn  = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)

br = br = Browser(factory=RobustFactory())
br.set_handle_robots(False)

Lifestream = lifestream.Lifestream()

# FOr each LOTRO character, add a line to the [lotro] section of the config file with the name and My.Lotro URL for it, like this:
# [lotro]
# berlique = http://my.lotro.com/home/character/2776943/150307637564818156/activitylog

DEBUG = False

for item in lifestream.config.items("lotro"):
	URL = item[1]

	if DEBUG:
		print item
	
	response = br.open(URL)
	html = br.response().read();
	soup = BeautifulSoup(html)

	table = soup.findAll("table", {"class":"gradient_table activitylog"})

	#print html

	title = True;

	lines = table[0].findAll("tr")

	if len(lines) < 3:
		if DEBUG:
			print "... Nothing there."
		continue

	for line in lines:
		if title:
			title = False
			continue
			
		char = line.find("td", {"class" : "char"}).findAll("a")[0].string
		date = line.find("td", {"class" : "date"}).string
		icon = line.find("td", {"class" : "details"}).findAll("img")[0].attrs[0][1]
		desc = line.find("td", {"class" : "details"}).findChildren(text=True)[1]
		
		if DEBUG:
			print "  Found %s" % desc
		
		if icon == "http://content.turbine.com/sites/playerportal/modules/lotro-base/images/icons/log/icon_quest.png":
			if DEBUG:
				print "   ... That's a quest. Nah."
			continue;

		text = "%s %s" % (char, desc)
		
		if DEBUG:
			print text
		parseddate = datetime.strptime(date+" 18:00", "%Y/%m/%d %H:%M")
		
		id = hashlib.md5()
		id.update(text.encode("utf-8"))
		
		Lifestream.add_entry("gaming", id.hexdigest(), text, "lotro", parseddate, url=URL, image=icon)
