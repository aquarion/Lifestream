#!/usr/bin/python

''' A handy script to import a CSV file from tfl.gov into lifestream, useful for catching up missed items '''

import lifestream
import sys
import pytz
import re
import hashlib
import time
import csv

from datetime import datetime

dbcxn  = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)

londontime    = pytz.timezone("Europe/London")

dataReader = csv.reader(open('oyster.csv', 'rb'))


s_sql = u'replace into lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`) values (%s, %s, %s, %s, %s, %s);'


headers = False;

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
		
		print action, utcdate
		cursor.execute(s_sql, ("oyster", id.hexdigest(), action, utcdate, "#", "oyster"))
