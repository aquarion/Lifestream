"""SwitchBot temperature/humidity sensor importer for Lifestream."""

import base64
import hashlib
import hmac
import uuid
from datetime import datetime, timezone

import requests

from lifestream.core import config
from lifestream.importers.base import BaseImporter


class SwitchBotAPI:
    """Client for the SwitchBot API.

    Uses v1.1's signed-request auth (v1.0's token-only auth is frozen —
    SwitchBot recommend all users migrate): each request is signed with
    HMAC-SHA256 over token+timestamp+nonce, using the account's secret key.
    """

    base_url = "https://api.switch-bot.com"
    token: str = ""
    secret: str = ""
    version = "v1.1"

    def __init__(self, token: str | None = None, secret: str | None = None) -> None:
        """Initialize with token/secret from config or parameters."""
        self.token = token or config.get("switchbot", "token")
        self.secret = secret or config.get("switchbot", "secret")

    def _signed_headers(self) -> dict[str, str]:
        t = str(int(datetime.now(timezone.utc).timestamp() * 1000))
        nonce = str(uuid.uuid4())
        string_to_sign = f"{self.token}{t}{nonce}".encode()
        sign = (
            base64.b64encode(
                hmac.new(self.secret.encode(), string_to_sign, hashlib.sha256).digest()
            )
            .decode()
            .upper()
        )
        return {
            "authorization": self.token,
            "sign": sign,
            "t": t,
            "nonce": nonce,
        }

    def call(self, method: str, callname: str, data: dict | None = None) -> dict:
        """Make an API call."""
        if data is None:
            data = {}
        url = f"{self.base_url}/{self.version}/{callname}"

        headers = self._signed_headers()

        if method == "post":
            headers["content-type"] = "application/json; charset=utf8"
            r = requests.post(url, json=data, headers=headers, timeout=30)
        elif method == "get":
            r = requests.get(url, params=data, headers=headers, timeout=30)
        else:
            raise ValueError(f"Unknown method: {method}")

        r.raise_for_status()
        return r.json()


class SwitchbotImporter(BaseImporter):
    """Import temperature and humidity data from SwitchBot sensors."""

    name = "switchbot"
    description = "Import temperature and humidity data from SwitchBot sensors"
    config_section = "switchbot"

    def validate_config(self) -> bool:
        """Ensure SwitchBot credentials are configured."""
        missing = [k for k in ("token", "secret") if not self.get_config(k)]
        if missing:
            self.logger.error(f"Missing SwitchBot config keys: {', '.join(missing)}")
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
