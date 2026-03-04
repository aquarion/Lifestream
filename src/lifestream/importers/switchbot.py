"""SwitchBot temperature/humidity sensor importer for Lifestream."""

from datetime import datetime

import requests

from lifestream.importers.base import BaseImporter
from lifestream.core import config


class SwitchBotAPI:
    """Client for the SwitchBot API."""

    base_url = "https://api.switch-bot.com"
    token: str = ""
    version = "v1.0"

    def __init__(self, token: str | None = None) -> None:
        """Initialize with token from config or parameter."""
        if token:
            self.token = token
        else:
            self.token = config.get("switchbot", "token")

    def call(self, method: str, callname: str, data: dict | None = None) -> dict:
        """Make an API call."""
        if data is None:
            data = {}
        url = f"{self.base_url}/{self.version}/{callname}"

        headers: dict[str, str] = {"authorization": self.token}

        if method == "post":
            headers["content-type"] = "application/json; charset=utf8"
            r = requests.post(url, data=data, headers=headers)
        elif method == "get":
            r = requests.get(url, params=data, headers=headers)
        else:
            raise ValueError(f"Unknown method: {method}")

        return r.json()


class SwitchbotImporter(BaseImporter):
    """Import temperature and humidity data from SwitchBot sensors."""

    name = "switchbot"
    description = "Import temperature and humidity data from SwitchBot sensors"
    config_section = "switchbot"

    def validate_config(self) -> bool:
        """Ensure SwitchBot token is configured."""
        if not self.get_config("token"):
            self.logger.error("No SwitchBot token in config")
            return False
        return True

    def run(self) -> None:
        """Import data from SwitchBot devices."""
        switchbot = SwitchBotAPI()

        r = switchbot.call("get", "devices")
        for device in r["body"]["deviceList"]:
            name = device["deviceName"]

            self.logger.info(f"Hello {name}, You are a {device['deviceType']}")

            if device["deviceType"] == "Meter":
                data = switchbot.call("get", f"devices/{device['deviceId']}/status")[
                    "body"
                ]

                self.logger.info(f"{name}-temp is {data['temperature']}")
                self.logger.info(f"{name}-humid is {data['humidity']}")

                self.entry_store.add_stat(
                    datetime.now(), f"{name}-temp", data["temperature"]
                )
                self.entry_store.add_stat(
                    datetime.now(), f"{name}-humid", data["humidity"]
                )


def main():
    """Entry point for CLI."""
    return SwitchbotImporter.main()


if __name__ == "__main__":
    exit(main())
