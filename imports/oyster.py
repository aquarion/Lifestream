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


if (len(sys.argv) < 3):
	print "Usage: %s class oystercard_number" % sys.argv[0]
	sys.exit(5)

TYPE          = sys.argv[1]
OYSTER_NUMBER = sys.argv[2]
USERNAME      = lifestream.config.get("oyster", "username")
PASSWORD      = lifestream.config.get("oyster", "password")

londontime    = pytz.timezone("Europe/London")

br = br = Browser(factory=RobustFactory())
br.set_handle_robots(False)

################ Login

response = br.open("https://oyster.tfl.gov.uk/oyster/entry.do")

br.select_form(name="sign-in")
br['j_password']=PASSWORD
br['j_username']=USERNAME
br.submit()

############### Card Choice

br.select_form(nr=0)
br['cardId']=[OYSTER_NUMBER,]
br.submit()

############### Dashboard

link=br.find_link(text="Journey history")
br.follow_link(link)

############### Journey History HTML


sleep(10)

html = br.response().read()

codes = re.findall("/oyster\/journeyDetailsPrint\.do\?_qv=(.*?)\"", html)

br.open("/oyster/journeyDetailsPrint.do?_qv=%s" % codes[1])

#br.open("/oyster/journeyDetailsPrint.do?_qv=fc1ee4cf11fc09bd332ba3cebada1fc468c89f5d");

############### Journey History CSV

data = br.response().read()

#Date,Start Time,End Time,Journey/Action,Charge,Credit,Balance,Note

s_sql = u'replace into lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`) values (%s, %s, %s, %s, %s, %s);'

headers = False

dataReader = csv.reader(StringIO.StringIO(data))
for row in dataReader:
	if not headers:
		headers = row
	else:
		date = row[0]
		time_from = row[1]
		time_to   = row[2]
		action    = row[3]
		charge    = row[4]
		credit    = row[5]
		balance   = row[6]
		note      = row[7]
		
		if not time_from and time_to:
			time_from = time_to
		elif not time_from:
			time_from = "00:00"
		
		#print row
		timestamp = datetime.strptime("%s %s" % (date, time_from), "%d-%b-%Y %H:%M")
		loc_date  = londontime.localize(timestamp)
		utcdate   = loc_date.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")
		
		id = hashlib.md5()
		id.update(utcdate)
		id.update(action)
		
		#print action, utcdate
		cursor.execute(s_sql, ("oyster", id.hexdigest(), action, utcdate, "#", "oyster"))
