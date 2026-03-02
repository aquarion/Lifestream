#!/usr/bin/python
# -*- coding: utf-8 -*-

import logging
from datetime import datetime

import requests

# Local
import lifestream
from lifestream.db import EntryStore

logger = logging.getLogger("switchbot")


# lifestream.arguments.add_argument(
#     '--reauth',
#     required=False,
#     help="Get new token",
#     default=False,
#     action='store_true')

# lifestream.arguments.add_argument(
#     '--catchup',
#     required=False,
#     help="Force sync of all achievements",
#     default=False,
#     action='store_true')


args = lifestream.parse_args()

entry_store = EntryStore()

# https://github.com/OpenWonderLabs/SwitchBotAPI


class SwitchBotAPI:

    base_url = "https://api.switch-bot.com"
    token: str = ""
    version = "v1.0"

    def __init__(self, token: str | None = None) -> None:
        if token:
            self.token = token
        else:
            self.token = lifestream.config.get("switchbot", "token")

    def call(self, method, callname, data=None):
        if data is None:
            data = {}
        URL = "{}/{}/{}".format(self.base_url, self.version, callname)

        headers: dict[str, str] = {"authorization": self.token}

        if method == "post":
            headers["content-type"] = "application/json; charset=utf8"
            r = requests.post(URL, data=data, headers=headers)
        elif method == "get":
            r = requests.get(URL, params=data, headers=headers)
        else:
            raise ValueError(f"Unknown method: {method}")

        return r.json()


switchbot = SwitchBotAPI()

r = switchbot.call("get", "devices")
for device in r["body"]["deviceList"]:

    name = device["deviceName"]

    logging.info("Hello {}, You are a {}".format(name, device["deviceType"]))
    if device["deviceType"] == "Meter":
        data = switchbot.call("get", "devices/{}/status".format(device["deviceId"]))[
            "body"
        ]

        logging.info("{}-temp is {}".format(name, data["temperature"]))
        logging.info("{}-humid is {}".format(name, data["humidity"]))

        entry_store.add_stat(
            datetime.now(), "{}-temp".format(name), data["temperature"]
        )
        entry_store.add_stat(
            datetime.now(), "{}-humid".format(name), data["humidity"]
        )
#
#    entry_store.add_stat(date, STATISTIC, dates[date]['total'])
