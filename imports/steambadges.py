#!/usr/bin/python
# Python
import sys
import pytz
from datetime import datetime
import hashlib
import logging
import signal

# Libraries
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.common.by import By

# Local
import lifestream


logger = logging.getLogger('Steam Badges')
args = lifestream.arguments.parse_args()

USERNAME = lifestream.config.get("steam", "username")
steamtime = pytz.timezone('US/Pacific')
Lifestream = lifestream.Lifestream()

options = FirefoxOptions()
options.add_argument('-headless')
browser = webdriver.Firefox(options=options)

# Login

URL = "https://steamcommunity.com/id/%s/badges?xml=1" % USERNAME

browser.get(URL)

s_sql = 'INSERT IGNORE INTO lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`, `image`) values (%s, %s, %s, %s, %s, %s, %s);'

#badges = browser.find_elements_by_css_selector("div.badge_row_inner")
badges = browser.find_elements(By.CSS_SELECTOR, "div.badge_row_inner")

for badge in badges:
    image = badge.find_element(By.CSS_SELECTOR, 
        ".badge_info_image img").get_attribute("src")
    text = badge.find_element(By.CLASS_NAME, "badge_info_title").text.strip()
    date = badge.find_element(By.CLASS_NAME, 
        "badge_info_unlocked").text.strip()[9:]

    try:
        parseddate = datetime.strptime(date, "%b %d, %Y @ %I:%M%p")
    except ValueError:
        try:
            parseddate = datetime.strptime(date, "%b %d @ %I:%M%p")
        except ValueError:
            print(date)
            print(URL)
            print(text)
            sys.exit(5)
    localdate = steamtime.localize(parseddate)
    utcdate = localdate.astimezone(pytz.utc)

    id = hashlib.md5()
    id.update(text.encode('utf8'))

    logger.info(text)

    Lifestream.add_entry(
        "badge",
        id.hexdigest(),
        text,
        "steam",
        utcdate,
        url=URL,
        image=image)


# kill the specific phantomjs child proc
try:
    if browser:
        browser.quit()                                      # quit the node proc
except AttributeError as e:
    logger.info("Failed to quit: %s" % e)
