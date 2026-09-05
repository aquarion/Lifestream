"""Destiny 2 importer for Lifestream, via Bungie's Platform API.

Logs each character's completed activities (missions, strikes, raids, etc.)
with the encountered activity's name/description/icon. Unlike the WoW
importer's Blizzard API, Bungie's Platform API endpoints used here are
still current and unchanged from the old script.
"""

import hashlib
from datetime import datetime, timedelta, timezone

import dateutil.parser
import requests

from lifestream.core import code_fetcher, set_backoff, should_backoff
from lifestream.importers.base import ConfigurationError, OAuthImporter

PLATFORM_BASE = "https://www.bungie.net/Platform"
AUTHORIZE_URL = "https://www.bungie.net/en/oauth/authorize"
TOKEN_URL = "https://www.bungie.net/platform/app/oauth/token/"

IMAGE_BASE = "https://www.bungie.net"

MEMBERSHIP_TYPES = {
    0: "None",
    1: "TigerXbox",
    2: "TigerPsn",
    3: "TigerSteam",
    4: "TigerBlizzard",
    10: "TigerDemon",
    254: "BungieNext",
    -1: "All",
}

THROTTLE_BACKOFF_KEY = "destiny2:api_error:throttled"


class DestinyException(Exception):
    """Base class for Bungie Platform API errors (ErrorStatus values)."""


class DestinyAccountNotFound(DestinyException):
    """Raised when a membership has no Destiny 2 account."""


class DestinyThrottledByGameServer(DestinyException):
    """Raised when Bungie's API reports we're being rate-limited."""


class Destiny2Importer(OAuthImporter):
    """Import Destiny 2 activity history from Bungie's Platform API."""

    name = "destiny2"
    description = "Import Destiny 2 activity history"
    config_section = "bungie"
    oauth_filename = "bungie.oauth"

    def validate_config(self) -> bool:
        """Ensure Bungie app credentials are configured."""
        missing = [
            k for k in ("key", "client_id", "client_secret") if not self.get_config(k)
        ]
        if missing:
            self.logger.error(f"Missing Bungie config keys: {', '.join(missing)}")
            return False
        return True

    def _fetch_auth_code(self) -> str:
        """Prompt the user through Bungie's OAuth authorize step and return
        the resulting authorization code."""
        try:
            code_fetcher.are_we_working()
            use_code_fetcher = True
        except code_fetcher.WeSayNotToday as e:
            raise ConfigurationError(
                "To catch a Destiny 2 OAuth redirect, configure [webserver] in config.ini"
            ) from e

        client_id = self.get_config("client_id")
        # Bungie's app config carries a single fixed redirect URI set in its
        # developer portal — there's no redirect_uri param on this URL.
        authorize_url = (
            f"{AUTHORIZE_URL}?client_id={client_id}&response_type=code"
            "&state=6i0mkLx79Hp91nzWVceHrzHG4"
        )
        print("Go to the following link in your browser:")
        print(authorize_url)
        print()

        if use_code_fetcher:
            return code_fetcher.get_code("code")["code"][0]
        print("If you configure [webserver], this is a lot easier.")
        return input("What is the PIN? ")

    @staticmethod
    def _with_expiry(token: dict) -> dict:
        now = datetime.now(timezone.utc)
        token["expire_dt"] = now + timedelta(seconds=int(token["expires_in"]))
        token["refresh_expire_dt"] = now + timedelta(
            seconds=int(token["refresh_expires_in"])
        )
        return token

    def _refresh_token(self, oauth_token: dict) -> dict:
        """Refresh an expired access token using its refresh token."""
        self.logger.info("Refreshing Destiny 2 access token...")
        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": oauth_token["refresh_token"],
                "client_id": self.get_config("client_id"),
                "client_secret": self.get_config("client_secret"),
            },
            timeout=30,
        )
        refreshed = response.json()

        if "error" in refreshed:
            if refreshed["error"] == "DestinyThrottledByGameServer":
                set_backoff(THROTTLE_BACKOFF_KEY)
            raise ConfigurationError(
                f"Error refreshing Destiny 2 token: {refreshed['error']} — "
                "run with --reauth"
            )

        refreshed = self._with_expiry(refreshed)
        self.save_oauth_token(refreshed)
        return refreshed

    def authenticate(self) -> dict:
        """
        Run Bungie's OAuth 2.0 flow (via the webserver's OAuth catcher, or a
        manual PIN) and return the token dict, refreshing/persisting it as
        needed.
        """
        oauth_token = None if self.args.reauth else self.load_oauth_token()

        if oauth_token:
            now = datetime.now(timezone.utc)
            try:
                expired = now > oauth_token["expire_dt"]
                refresh_expired = now > oauth_token["refresh_expire_dt"]
            except TypeError as e:
                # The saved token predates this importer (e.g. still-present
                # imports/destiny2.py, which shares the same bungie.oauth
                # file and stores naive datetimes) and can't be compared
                # against a timezone-aware "now" — treat it as unusable
                # rather than crashing.
                raise ConfigurationError(
                    "Destiny 2 token file is in an old/incompatible format — "
                    "run with --reauth"
                ) from e
            if expired:
                if refresh_expired:
                    raise ConfigurationError(
                        "Destiny 2 refresh token has expired — run with --reauth"
                    )
                oauth_token = self._refresh_token(oauth_token)
            return oauth_token

        auth_code = self._fetch_auth_code()

        response = requests.post(
            TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": auth_code,
                "client_id": self.get_config("client_id"),
                "client_secret": self.get_config("client_secret"),
            },
            timeout=30,
        )
        response.raise_for_status()
        oauth_token = self._with_expiry(response.json())

        self.save_oauth_token(oauth_token)
        return oauth_token

    def destiny_call(
        self, credentials: dict, path: str, params: dict | None = None
    ) -> dict:
        """Call a Bungie Platform API endpoint and return its Response body."""
        url = f"{PLATFORM_BASE}/{path}"
        headers = {
            "X-API-Key": self.get_config("key"),
            "Authorization": f"{credentials['token_type']} {credentials['access_token']}",
        }
        response = requests.get(url, headers=headers, params=params or {}, timeout=30)
        response.raise_for_status()
        result = response.json()

        if result["ErrorCode"] != 1:
            self.logger.warning(result.get("Message", result["ErrorStatus"]))
            error_cls = {
                "DestinyAccountNotFound": DestinyAccountNotFound,
                "DestinyThrottledByGameServer": DestinyThrottledByGameServer,
            }.get(result["ErrorStatus"], DestinyException)
            raise error_cls(result["ErrorStatus"])

        return result.get("Response", {})

    def destiny_entity(self, credentials: dict, entity_type: str, hash_id: int) -> dict:
        """Look up a Destiny manifest entity (e.g. an activity definition)."""
        return self.destiny_call(
            credentials, f"Destiny2/Manifest/{entity_type}/{hash_id}/"
        )

    @staticmethod
    def _activity_entry_id(character_id: str, activity_hash: int) -> str:
        return hashlib.md5(
            f"destiny2{character_id}{activity_hash}".encode()
        ).hexdigest()

    def log_activity(
        self, instance: dict, activity: dict, character_id: str, character_data: dict
    ) -> None:
        """Persist a single completed activity instance as an entry."""
        display = activity["displayProperties"]
        if "name" not in display:
            self.logger.warning("Activity doesn't have a name, skipping")
            return

        activity_hash = instance["activityDetails"]["referenceId"]
        text = f"{display['name']} --- {display.get('description', '')}"
        utcdate = dateutil.parser.parse(instance["period"]).astimezone(timezone.utc)

        if display.get("hasIcon"):
            image = IMAGE_BASE + display["icon"]
        else:
            image = IMAGE_BASE + character_data.get("emblemPath", "")

        self.logger.info("Completed %s at %s", display["name"], instance["period"])
        self.entry_store.add_entry(
            "gaming",
            self._activity_entry_id(character_id, activity_hash),
            text,
            "destiny2",
            utcdate,
            url="",
            image=image,
            fulldata_json={"instance_info": instance, "activity_info": activity},
        )

    def process_character(
        self,
        credentials: dict,
        member_data: dict,
        character_id: str,
        character_data: dict,
    ) -> None:
        """Log every completed activity for one character."""
        path = (
            f"Destiny2/{member_data['membershipType']}/Account/"
            f"{member_data['membershipId']}/Character/{character_id}/Stats/Activities/"
        )
        try:
            activities = self.destiny_call(
                credentials, path, {"count": 100, "mode": "None", "page": 0}
            )
        except DestinyThrottledByGameServer:
            set_backoff(THROTTLE_BACKOFF_KEY)
            raise

        for instance in activities.get("activities", []):
            try:
                if instance["values"]["completed"]["basic"]["value"] == 0:
                    continue

                activity = self.destiny_entity(
                    credentials,
                    "DestinyActivityDefinition",
                    instance["activityDetails"]["referenceId"],
                )
                if not activity:
                    self.logger.warning("Activity definition was empty, skipping")
                    continue

                self.log_activity(instance, activity, character_id, character_data)
            except DestinyThrottledByGameServer:
                set_backoff(THROTTLE_BACKOFF_KEY)
                raise
            except Exception as e:
                # One malformed/unexpected activity instance shouldn't stop
                # the rest of this character's activities from being logged.
                self.logger.error("Failed to process an activity instance: %s", e)

    def process_membership(self, credentials: dict, member_data: dict) -> bool:
        """Process every character under one membership. Returns True if a
        throttle error was hit and the caller should stop the whole run."""
        membership_type_name = MEMBERSHIP_TYPES.get(
            member_data["membershipType"], member_data["membershipType"]
        )
        self.logger.info("Looking at membership for %s", membership_type_name)

        try:
            profile = self.destiny_call(
                credentials,
                f"Destiny2/{member_data['membershipType']}/Profile/"
                f"{member_data['membershipId']}/",
                {"components": "Characters"},
            )
        except DestinyAccountNotFound:
            self.logger.info(
                "Membership for %s doesn't have Destiny 2", membership_type_name
            )
            return False
        except DestinyThrottledByGameServer:
            set_backoff(THROTTLE_BACKOFF_KEY)
            self.logger.warning("Throttled by Bungie's API, stopping this run")
            return True

        characters = profile["characters"]["data"]
        for character_id, character_data in characters.items():
            try:
                self.process_character(
                    credentials, member_data, character_id, character_data
                )
            except DestinyThrottledByGameServer:
                # set_backoff was already called wherever this was raised
                # (process_character/destiny_call) — just stop.
                self.logger.warning("Throttled by Bungie's API, stopping this run")
                return True
            except Exception as e:
                self.logger.error("Failed to process character %s: %s", character_id, e)
        return False

    def run(self) -> None:
        """Import completed activities for every character on the account."""
        if should_backoff(THROTTLE_BACKOFF_KEY):
            self.logger.warning("Backing off after a recent throttle error")
            return

        credentials = self.authenticate()

        try:
            memberships = self.destiny_call(
                credentials, "User/GetMembershipsForCurrentUser/"
            )
        except DestinyThrottledByGameServer:
            set_backoff(THROTTLE_BACKOFF_KEY)
            raise

        for member_data in memberships.get("destinyMemberships", []):
            if self.process_membership(credentials, member_data):
                return


def main():
    """Entry point for CLI."""
    return Destiny2Importer.main()


if __name__ == "__main__":
    exit(main())
