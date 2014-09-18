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

Lifestream = lifestream.Lifestream()

if (len(sys.argv) < 2):
    print "Usage: %s filename" % sys.argv[0]
    sys.exit(5)

londontime = pytz.timezone("Europe/London")

# Date,Start Time,End Time,Journey/Action,Charge,Credit,Balance,Note

headers = False

data = open(sys.argv[1], 'rb')
dataReader = csv.reader(data)
for row in dataReader:
    if not headers:
        headers = row
    else:
        date = row[0]
        time_from = row[1]
        time_to = row[2]
        action = row[3]
        charge = row[4]
        credit = row[5]
        balance = row[6]
        note = row[7]

        if not time_from and time_to:
            time_from = time_to
        elif not time_from:
            time_from = "00:00"

        timestamp = datetime.strptime(
            "%s %s" %
            (date, time_from), "%d-%b-%Y %H:%M")
        loc_date = londontime.localize(timestamp)
        utcdate = loc_date.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")

        id = hashlib.md5()
        id.update(utcdate)
        id.update(action)

        print action, utcdate
        #add_entry(self, type, id, title, source, date, url='', image='', fulldata_json=False, update=False)
        Lifestream.add_entry(
            "oyster",
            id.hexdigest(),
            action,
            "oyster",
            utcdate,
            False,
            False,
            row)

data.close()
