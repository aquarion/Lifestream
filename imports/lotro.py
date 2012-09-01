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

s_sql = u'REPLACE INTO lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`, `image`) values (%s, %s, %s, %s, %s, %s, %s);'

# FOr each LOTRO character, add a line to the [lotro] section of the config file with the name and My.Lotro URL for it, like this:
# [lotro]
# berlique = http://my.lotro.com/home/character/2776943/150307637564818156/activitylog


for item in lifestream.config.items("lotro"):
	URL = item[1]
	
	response = br.open(URL)
	html = br.response().read();
	soup = BeautifulSoup(html)

	table = soup.findAll("table", {"class":"gradient_table activitylog"})

	#print html

	title = True;

	lines = table[0].findAll("tr")
	for line in lines:
		if title:
			title = False
			continue
			
		char = line.find("td", {"class" : "char"}).findAll("a")[0].string
		date = line.find("td", {"class" : "date"}).string
		icon = line.find("td", {"class" : "details"}).findAll("img")[0].attrs[0][1]
		desc = line.find("td", {"class" : "details"}).findChildren(text=True)[1]
		
		text = "%s %s" % (char, desc)
		
		parseddate = datetime.strptime(date+" 18:00", "%Y/%m/%d %H:%M")
		
		id = hashlib.md5()
		id.update(text.encode("utf-8"))
		
		cursor.execute(s_sql, ("gaming", id.hexdigest(), text, parseddate, URL, "lotro", icon))
		#print s_sql % ("gaming", id.hexdigest(), text, parseddate, URL, "lotro", icon)