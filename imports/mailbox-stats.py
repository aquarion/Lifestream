#!/usr/bin/python

import lifestream, lifestreamutils

import mailbox
import email
import datetime
import time

import sys

if (len(sys.argv) < 2):
	print "Usage: %s statistic filename" % (sys.argv[0])
	sys.exit(5)
	
STATISTIC = sys.argv[1]
FILENAME  = sys.argv[2]

DEBUG = False

dbcxn  = lifestream.getDatabaseConnection()
cursor = lifestream.cursor(dbcxn)

inbox = mailbox.mbox(FILENAME)

dates = {}
datekeys = []

length = len(inbox)
count  = 0.0

if DEBUG:
	print FILENAME
	print "0%"

for key in inbox.iterkeys():
	count += 1
	msg = inbox[key]
	if not msg or not msg['From']:
		continue
		
	try:
		subject = msg['Subject'][0:64]
	except:
		subject = "No Subject";
		
	try:
		dte = datetime.datetime.fromtimestamp(time.mktime(email.utils.parsedate(msg['Date'])))
	except:
		continue
		
	iso = dte.strftime("%Y-%m-%d")
	if iso in datekeys:
		dates[iso]['total'] += 1
	else:
		dates[iso] = {'total': 1 }
		datekeys.append(iso)
	if DEBUG:
		sys.stdout.write('%3.2f%% - %s\r' % ((count/length) * 100,  ""))
		sys.stdout.flush()

if DEBUG:
	print "100%"
	print "Databasing...."

for date in dates.keys():
	lifestreamutils.newstat(date, STATISTIC, dates[date]['total'])
