#!/usr/bin/python
# Python
import datetime
import email

# Libraries
import mailbox
import sys
import time

# Local
from lifestream.db import EntryStore

entry_store = EntryStore()

if len(sys.argv) < 2:
    print("Usage: %s statistic filename" % (sys.argv[0]))
    sys.exit(5)

STATISTIC = sys.argv[1]
FILENAME = sys.argv[2]

DEBUG = False

inbox = mailbox.mbox(FILENAME)

dates = {}
datekeys = []

length = len(inbox)
count = 0.0

if DEBUG:
    print(FILENAME)
    print("0%")

for key in inbox.keys():
    count += 1
    msg = inbox[key]
    if not msg or not msg["From"]:
        continue

    try:
        subject = msg["Subject"][0:64]
    except Exception:  # TODO: narrow down to TypeError, KeyError
        subject = "No Subject"

    try:
        dte = datetime.datetime.fromtimestamp(
            time.mktime(email.utils.parsedate(msg["Date"]))
        )
    except Exception:  # TODO: narrow down to TypeError, ValueError
        continue

    iso = dte.strftime("%Y-%m-%d")
    if iso in datekeys:
        dates[iso]["total"] += 1
    else:
        dates[iso] = {"total": 1}
        datekeys.append(iso)
    if DEBUG:
        sys.stdout.write("%3.2f%% - %s\r" % ((count / length) * 100, ""))
        sys.stdout.flush()

if DEBUG:
    print("100%")
    print("Databasing....")

for date in list(dates.keys()):
    entry_store.add_stat(date, STATISTIC, dates[date]["total"])
