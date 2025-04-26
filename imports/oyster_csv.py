#!/usr/bin/python
# Python
import csv
import hashlib
import logging
from datetime import datetime

import pytz

# Local
import lifestream

# Libraries



Lifestream = lifestream.Lifestream()


logger = logging.getLogger("Oyster-CSV")
lifestream.arguments.add_argument("filename")
args = lifestream.arguments.parse_args()

londontime = pytz.timezone("Europe/London")

# Date,Start Time,End Time,Journey/Action,Charge,Credit,Balance,Note

headers = False

data = open(args.filename, "rt")
dataReader = csv.reader(data)
for row in dataReader:
    if not row:
        continue
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

        timestamp = datetime.strptime("%s %s" % (date, time_from), "%d-%b-%Y %H:%M")
        loc_date = londontime.localize(timestamp)
        utcdate = loc_date.astimezone(pytz.utc).strftime("%Y-%m-%d %H:%M")

        id = hashlib.md5()
        id.update(utcdate.encode("utf-8"))
        id.update(action.encode("utf-8"))

        logger.info("%s: %s" % (action, utcdate))
        # add_entry(self, type, id, title, source, date, url='', image='', fulldata_json=False, update=False)
        Lifestream.add_entry(
            "oyster", id.hexdigest(), action, "oyster", utcdate, False, False, row
        )

data.close()
