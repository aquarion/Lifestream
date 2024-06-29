#!/usr/bin/python
# Python
from ctypes.wintypes import CHAR
from datetime import datetime
import logging
import hashlib
import re
import math

from pprint import pprint

# Libraries
import requests
import ipdb
import bs4
import simplejson
import sqlite3

# Local
import lifestream


Lifestream = lifestream.Lifestream()

APIKEY = Lifestream.config.get("xivapi", "apikey")
CHARACTERS = Lifestream.config.get("xivapi", "characters")
ICON_BASE = Lifestream.config.get("xivapi", "icon_base")

logger = logging.getLogger('FFXIV')
args = lifestream.arguments.parse_args()


class Lodestone:

    api_key = False
    base_url = "https://xivapi.com"
    languages = ["en", "fr", "de", "ja"]

    achivement_db = False;

    def __init__(self, apikey) -> None:
        self.api_key = apikey
        self.achivement_db = sqlite3.connect(Lifestream.config.get("xivapi", "achievement_db"))
        pass

    def get_character_detail(self, character_id, section="", page=1, region="eu"):
        url = "https://{}.finalfantasyxiv.com/lodestone/character/{}/{}".format(region, character_id, section)
        params = {}
        if page > 1:
            params['page'] = page

        request = requests.get(url, params)
        return request.text
    
    def pull_value(self, map, root):
        tags = root.select(map['selector'])
        if not len(tags):
            raise Exception("Selector not found: {}".format(map['selector']))
        
        if 'regex' in map:
            if "attribute" in map:
                haystack = tags[0].get(map['attribute'])
            else:
                haystack = tags[0].text.strip()

            re_result = re.findall(map['regex'], haystack)
            if len(re_result) > 0:
                return re_result[0]
            else:
                raise Exception("Regex not found: {}".format(map['regex']))
        if 'multiple' in map: 
            return tags
        else:
            
            if "attribute" in map:
                return tags[0].get(map['attribute'])
            else:
                return tags[0]

    def get_character_info(self, character_id):
        html = self.get_character_detail(character_id)
        map = simplejson.load(open('datafiles/lodestone-css-selectors/profile/character.json'))
        soup = bs4.BeautifulSoup(html, 'html.parser')

        character = {}
        character['Name'] = self.pull_value(map['NAME'], soup).text
        character['Server'] = self.pull_value(map['SERVER'], soup)
        character['Title'] = self.pull_value(map['TITLE'], soup).text
        return character
    
    def get_achievements(self, character_id):
        html = self.get_character_detail(character_id, "achievement")
        achievements = self.parse_achievements_page(html)
        while self.next:
            logger.debug("Fetching next page {}".format(self.next))
            next_page_contents = requests.get(self.next).text
            achievements += self.parse_achievements_page(next_page_contents)

        return achievements

    def icon_path(self, achivement_id):

        result = self.achivement_db.execute("SELECT icon FROM achievements WHERE id = ?", (achivement_id,))
        row = result.fetchone()
        if row:
            icon_id = int(row[0])
        else:
            logger.warning("Achivement DB Icon not found for {}".format(achivement_id))
            return False
        
        filename = "{:06d}".format(icon_id)
        foldername = "{:06d}".format(math.floor(icon_id/1000)*1000)

        return "{}/{}.png".format(foldername, filename)

    def parse_achievements_page(self, html):
        map = simplejson.load(open('datafiles/lodestone-css-selectors/profile/achievements.json'))
        soup = bs4.BeautifulSoup(html, 'html.parser')

        root = self.pull_value(map['ROOT'], soup)
        entries = self.pull_value(map['ENTRY']['ROOT'], root)

        
        self.next = self.pull_value(map['LIST_NEXT_BUTTON'], root)
        if self.next == "javascript:void(0);":
            self.next = False        
            
        achievements = []
        for entry in entries:
            achivement = {}
            achivement['Name'] = self.pull_value(map['ENTRY']['NAME'], entry)[1]
            achivement['ID'] = self.pull_value(map['ENTRY']['ID'], entry)
            achivement['Icon'] = self.icon_path(self.pull_value(map['ENTRY']['ID'], entry))
            date_epoch = self.pull_value(map['ENTRY']['TIME'], entry)
            achivement['Date'] =  datetime.fromtimestamp(int(date_epoch))
            achievements.append(achivement)
        
        return achievements


lodestone = Lodestone(APIKEY)

def update_achievements(char_id):
    achievements = lodestone.get_achievements(char_id)
    character = lodestone.get_character_info(char_id)
    character_name = character['Name']

    for achivement in achievements:
        logger.debug("{}, {}, {}".format(achivement['Name'], achivement['Icon'], achivement['Date']))
        
    
        message = "FFXIV: {} &ndash; {}".format(character_name, achivement['Name'])

        url = 'https://eu.finalfantasyxiv.com/lodestone/character/{}/achievement/detail/{}/'.format(char_id, achivement['ID'])

        Lifestream.add_entry(
            type="achivement",
            id="ffxiv-{}-{}".format(char_id, achivement['ID']),
            title=message,
            source="FFXIV",
            url=url,
            date=achivement['Date'],
            image="{}{}".format(ICON_BASE,achivement['Icon']),
            update=True)
        

if __name__ == '__main__':
    for character_id in CHARACTERS.split(","):
        update_achievements(character_id)


