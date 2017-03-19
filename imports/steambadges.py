#!/usr/bin/python
# Python
import sys
import pytz
from datetime import datetime
from time import sleep
import hashlib
import logging
import signal

# Libraries
from selenium import webdriver

# Local
import lifestream


logger = logging.getLogger('Steam Badges')
args = lifestream.arguments.parse_args()

USERNAME = lifestream.config.get("steam", "username")
steamtime = pytz.timezone('US/Pacific')
Lifestream = lifestream.Lifestream()

browser = webdriver.PhantomJS()

# Login

URL = "http://steamcommunity.com/id/%s/badges?xml=1" % USERNAME

browser.get(URL)

s_sql = u'INSERT IGNORE INTO lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`, `image`) values (%s, %s, %s, %s, %s, %s, %s);'

badges = browser.find_elements_by_css_selector("div.badge_row_inner")

for badge in badges:
    image = badge.find_element_by_css_selector(".badge_info_image img").get_attribute("src")
    text = badge.find_element_by_class_name("badge_info_title").text.strip()
    date = badge.find_element_by_class_name("badge_info_unlocked").text.strip()[9:]

    try:
        parseddate = datetime.strptime(date, "%b %d, %Y @ %I:%M%p")
    except ValueError:
	try:
        	parseddate = datetime.strptime(date, "%b %d @ %I:%M%p")
	except ValueError:
		print date
		print URL
		print text
		sys.exit(5)
    localdate = steamtime.localize(parseddate)
    utcdate = localdate.astimezone(pytz.utc)

    id = hashlib.md5()
    id.update(text)

    logger.info(text)

    Lifestream.add_entry(
        "badge",
        id.hexdigest(),
        text,
        "steam",
        utcdate,
        url=URL,
        image=image)


browser.service.process.send_signal(signal.SIGTERM) # kill the specific phantomjs child proc
browser.quit()                                      # quit the node proc
