#!/usr/bin/python
# Python
import hashlib
import logging
from datetime import datetime

# Libraries
from BeautifulSoup import BeautifulSoup
from mechanize import Browser, RobustFactory

# Local
import lifestream

Lifestream = lifestream.Lifestream()

CHARACTERS = Lifestream.config.get("thesecretworld", "characters")

br = br = Browser(factory=RobustFactory())
br.set_handle_robots(False)

# Login

logger = logging.getLogger("TSW")
args = lifestream.arguments.parse_args()

for character in CHARACTERS.split(","):

    url = "http://chronicle.thesecretworld.com/character/%s" % character

    response = br.open(url)

    html = br.response().read()

    soup = BeautifulSoup(html)

    rank = soup.findAll("div", {"class": "x6"})

    rank = rank[0]

    img = rank.findAll("img")[0]

    src = img.attrs[0][1]

    rank_n = rank.findAll("div", {"class": "rank wf"})[0]
    rank_t = rank.findAll("div", {"class": "title wf"})[0]

    text = "%s achieved %s&ndash;%s" % (
        character, rank_n.string, rank_t.string)

    logger.info(text)

    id = hashlib.md5()
    id.update(text)
    Lifestream.add_entry(
        "gaming",
        id.hexdigest(),
        text,
        "The Secret World",
        datetime.now(),
        url=url,
        image=src,
    )
