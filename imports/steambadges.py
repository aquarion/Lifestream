#!/usr/bin/python

import lifestream
import sys
from BeautifulSoup import BeautifulSoup
import pytz

import hashlib

from datetime import datetime

from mechanize import Browser, RobustFactory

from time import sleep

USERNAME = lifestream.config.get("steam", "username")
steamtime = pytz.timezone('US/Pacific')
Lifestream = lifestream.Lifestream()

br = br = Browser(factory=RobustFactory())
br.set_handle_robots(False)

# Login

URL = "http://steamcommunity.com/id/%s/badges?xml=1" % USERNAME

response = br.open(URL)

html = br.response().read()

s_sql = u'INSERT IGNORE INTO lifestream (`type`, `systemid`, `title`, `date_created`, `url`, `source`, `image`) values (%s, %s, %s, %s, %s, %s, %s);'

soup = BeautifulSoup(html)

badges = soup.findAll("div", {"class": "badge_row_inner"})

for badge in badges:
    image = badge.findAll(
        "div", {
            "class": "badge_info_image"})[0].findAll("img")[0].attrs[0][1]
    name = badge.findAll(
        "div", {
            "class": "badge_info_title"})[0].string.strip()
    date = badge.findAll(
        "div", {
            "class": "badge_info_unlocked"})[0].string.strip()[
        10:]

    #text = "%s &mdash; %s" % (name, desc)
    text = name

    try:
        parseddate = datetime.strptime(date, "%b %d, %Y @ %I:%M%p")
    except ValueError:
        parseddate = datetime.strptime(date, "%b %d @ %I:%M%p")
    localdate = steamtime.localize(parseddate)
    utcdate = localdate.astimezone(pytz.utc)

    id = hashlib.md5()
    id.update(text)

    Lifestream.add_entry(
        "badge",
        id.hexdigest(),
        text,
        "steam",
        utcdate,
        url=URL,
        image=image)
