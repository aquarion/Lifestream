#!/usr/bin/python
# Python
from ctypes.wintypes import CHAR
from datetime import datetime
import logging
import asyncio
import aiohttp
import hashlib

from pprint import pprint

# Libraries
import pyxivapi
import requests
import ipdb

from pyxivapi.exceptions import (
    XIVAPIBadRequest, XIVAPIForbidden, XIVAPINotFound, XIVAPIServiceUnavailable, 
    XIVAPIInvalidLanguage, XIVAPIError, XIVAPIInvalidIndex, XIVAPIInvalidColumns, 
    XIVAPIInvalidAlgo
)

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

    def __init__(self, apikey) -> None:
        self.api_key = apikey
        pass

    # The official client doesn't offer this as an endpoint, but we want to grab the achivements without doing 100 calls, so...
    def index_by_ids(self, index, ids: list, columns=(), language="en", page=1, per_page=100, all_pages=False):
        """|coro|
        Request data from a given index by ID.
        Parameters
        ------------
        index: str
            The index to which the content is attributed.
        content_id: int
            The ID of the content
        Optional[columns: list]
            A named list of columns to return in the response. ID, Name, Icon & ItemDescription will be returned by default.
            e.g. ["ID", "Name", "Icon"]
        Optional[language: str]
            The two character length language code that indicates the language to return the response in. Defaults to English (en).
            Valid values are "en", "fr", "de" & "ja"
        """
        if index == "":
            raise XIVAPIInvalidIndex("Please specify an index to search on, e.g. \"Item\"")

        if len(columns) == 0:
            raise XIVAPIInvalidColumns("Please specify at least one column to return in the resulting data.")

        params = {
            "private_key": self.api_key,
            "language": language,
            "ids" : ",".join(str(element) for element in ids),
            "limit" : per_page
        }

        if len(columns) > 0:
            params["columns"] = ",".join(list(set(columns)))

        url = f'{self.base_url}/{index}'

        response = requests.get(url, params=params)
        response_data = response.json();

        if all_pages and response_data['Pagination']['PageNext']:
            results = response_data['Results']
            while response_data['Pagination']['PageNext']:
                logger.debug("Page {}".format(response_data['Pagination']['PageNext']))
                next_page_params = params.copy()
                params['page'] = response_data['Pagination']['PageNext']
                response = requests.get(url, params=params)
                response_data = response.json();
                results += response_data['Results']

            return { 
                'Results': results,
                'Pagination' : "Nope"
            }
        else:
            return response_data


lodestone = Lodestone(APIKEY)

async def fetch_results(char_id):
    client = pyxivapi.XIVAPIClient(APIKEY)
    # Search Lodestone for a character
    character = await client.character_by_id(
        lodestone_id=char_id, 
        include_achievements=True
        # extended=True,
        # include_freecompany=True
    )

    await client.session.close()
    
    character_name = character['Character']['Name'];

    achivement_dates = {}
    achivements = character['Achievements']['List'] #[0:5]
    
    for achivement in achivements:
        achivement_dates[achivement['ID']] = achivement['Date']

    achivement_data = lodestone.index_by_ids(
        index="Achievement", 
        ids=achivement_dates.keys(), 
        columns=["ID", "Name", "Icon", "Category.Name"], 
        language="en", all_pages=True)

    results = {}
    for achivement in achivement_data['Results']:
        # pprint(achivement_dates[achivement['ID']])
        # try:
        #     pprint(achivement['ID'])
        # except Exception as e:
        #     ipdb.set_trace()
        achivement['Date'] = achivement_dates[achivement['ID']]
        results[achivement['ID']] = achivement
        
        logger.debug("{}, {}, {}".format(achivement['Name'], achivement['Icon'], datetime.fromtimestamp(achivement['Date'])))
        
    
        message = "FFXIV: {} &ndash; {}".format(character_name, achivement['Name'])

        url = 'https://eu.finalfantasyxiv.com/lodestone/character/{}/achievement/detail/{}/'.format(char_id, achivement['ID'])

        Lifestream.add_entry(
            type="achivement",
            id="ffxiv-{}-{}".format(char_id, achivement['ID']),
            title=message,
            source="FFXIV",
            url=url,
            date=datetime.fromtimestamp(achivement['Date']),
            image="{}{}".format(ICON_BASE,achivement['Icon']),
            update=True)
        

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.run_until_complete(fetch_results(CHARACTERS))

