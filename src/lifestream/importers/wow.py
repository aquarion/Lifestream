"""World of Warcraft importer for Lifestream, via Blizzard's Battle.net API.

Logs each character's completed achievements. Blizzard retired the old
Community API's per-character "feed" endpoint (which the previous version of
this importer used for incremental syncing), with no replacement — the
current Game Data/Profile API only exposes a character's full achievement
list, not a log of recent activity. So this importer always fetches the full
list on every run and relies on EntryStore.add_entry's existing
dedup-by-systemid to skip achievements already logged, checking
EntryStore.get_by_id first to also skip the (paid, rate-limited) detail/icon
lookups for achievements it's already seen.
"""

import hashlib
from datetime import datetime, timezone

import requests
from oauthlib.oauth2 import BackendApplicationClient
from requests.auth import HTTPBasicAuth
from requests_oauthlib import OAuth2Session

from lifestream.core import code_fetcher
from lifestream.importers.base import ConfigurationError, OAuthImporter

# Blizzard's Battle.net OAuth scope for reading a user's WoW character data.
SCOPE = "wow.profile"

# Default locale for achievement names/descriptions.
LOCALE = "en_US"


class WowCharacterNotFound(Exception):
    """Raised when a character isn't found (deleted, renamed, transferred realms)."""


class WowAchievementNotFound(Exception):
    """Raised when an achievement id has no Game Data entry (rare, but retired
    achievements do happen)."""


class WowImporter(OAuthImporter):
    """Import World of Warcraft character achievements from Battle.net."""

    name = "wow"
    description = "Import World of Warcraft character achievements"
    config_section = "blizzard"
    oauth_filename = "blizzard_user.oauth"

    def validate_config(self) -> bool:
        """Ensure Blizzard app credentials are configured."""
        missing = [k for k in ("key", "secret", "region") if not self.get_config(k)]
        if missing:
            self.logger.error(f"Missing Blizzard config keys: {', '.join(missing)}")
            return False
        return True

    def _oauth_base(self) -> str:
        return f"https://{self.get_config('region')}.battle.net"

    def _api_base(self) -> str:
        return f"https://{self.get_config('region')}.api.blizzard.com"

    def _redirect_uri(self) -> str:
        try:
            code_fetcher.are_we_working()
            return code_fetcher.get_url()
        except code_fetcher.WeSayNotToday as e:
            raise ConfigurationError(
                "To catch a WoW OAuth redirect, configure [webserver] in config.ini"
            ) from e

    def authenticate_user(self) -> dict:
        """
        Run Blizzard's OAuth 2.0 authorization-code flow (via the webserver's
        OAuth catcher) and return the user token dict, refreshing/persisting
        it as needed.
        """
        key = self.get_config("key")
        secret = self.get_config("secret")

        oauth_token = None if self.args.reauth else self.load_oauth_token()
        if oauth_token:
            return oauth_token

        redirect_uri = self._redirect_uri()

        oauth = OAuth2Session(key, redirect_uri=redirect_uri, scope=SCOPE)
        authorization_url, state = oauth.authorization_url(
            f"{self._oauth_base()}/oauth/authorize"
        )

        # intentional: user must visit this URL to complete OAuth; contains
        # no secret, only the public client key, redirect_uri, and scope
        print("Go to the following link in your browser:")
        print(authorization_url)  # codeql[py/clear-text-logging-sensitive-data]
        print()

        params = code_fetcher.get_code("code")
        if params.get("state", [None])[0] != state:
            raise ConfigurationError(
                "OAuth state mismatch on WoW callback — possible CSRF, aborting"
            )
        auth_code = params["code"][0]

        response = requests.post(
            f"{self._oauth_base()}/oauth/token",
            data={
                "redirect_uri": redirect_uri,
                "scope": SCOPE,
                "grant_type": "authorization_code",
                "code": auth_code,
            },
            auth=HTTPBasicAuth(key, secret),
            timeout=30,
        )
        response.raise_for_status()
        oauth_token = response.json()
        oauth_token["created_at"] = datetime.now(timezone.utc).isoformat()

        self.save_oauth_token(oauth_token)
        return oauth_token

    def fetch_app_token(self) -> str:
        """Fetch a fresh client-credentials app token for Game Data (static
        achievement/media) lookups. Not cached across runs — it's a single
        cheap call, not worth the complexity of the old script's disk cache."""
        key = self.get_config("key")
        secret = self.get_config("secret")

        client = BackendApplicationClient(client_id=key)
        oauth = OAuth2Session(client=client)
        token = oauth.fetch_token(
            token_url=f"{self._oauth_base()}/oauth/token",
            client_id=key,
            client_secret=secret,
        )
        return token["access_token"]

    def get_account_characters(self, user_token: str) -> list[dict]:
        """List every character across all WoW accounts linked to this user."""
        response = requests.get(
            f"{self._api_base()}/profile/user/wow",
            params={
                "namespace": f"profile-{self.get_config('region')}",
                "locale": LOCALE,
                "access_token": user_token,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        characters = []
        for account in data.get("wow_accounts", []):
            characters.extend(account.get("characters", []))
        return characters

    def get_character_achievements(
        self, user_token: str, character: dict
    ) -> list[dict]:
        """List a character's completed achievements (id + completion time)."""
        realm_slug = character["realm"]["slug"]
        name = character["name"]
        response = requests.get(
            f"{self._api_base()}/profile/wow/character/{realm_slug}/{name}/achievements",
            params={
                "namespace": f"profile-{self.get_config('region')}",
                "locale": LOCALE,
                "access_token": user_token,
            },
            timeout=30,
        )
        if response.status_code == 404:
            raise WowCharacterNotFound(f"{name} on {realm_slug}")
        response.raise_for_status()
        return response.json().get("achievements", [])

    def get_achievement_detail(self, app_token: str, achievement_id: int) -> dict:
        """Look up an achievement's name/description."""
        response = requests.get(
            f"{self._api_base()}/data/wow/achievement/{achievement_id}",
            params={
                "namespace": f"static-{self.get_config('region')}",
                "locale": LOCALE,
                "access_token": app_token,
            },
            timeout=30,
        )
        if response.status_code == 404:
            raise WowAchievementNotFound(f"achievement {achievement_id}")
        response.raise_for_status()
        return response.json()

    def get_achievement_icon(self, app_token: str, achievement_id: int) -> str:
        """Look up an achievement's icon URL, or "" if it has none."""
        response = requests.get(
            f"{self._api_base()}/data/wow/media/achievement/{achievement_id}",
            params={
                "namespace": f"static-{self.get_config('region')}",
                "access_token": app_token,
            },
            timeout=30,
        )
        response.raise_for_status()
        for asset in response.json().get("assets", []):
            if asset.get("key") == "icon":
                return asset.get("value", "")
        return ""

    @staticmethod
    def _achievement_entry_id(achievement_id: int) -> str:
        return hashlib.md5(f"{achievement_id}-wow".encode("utf8")).hexdigest()

    def log_achievement(
        self, achievement_id: int, completed_ms: int, character: dict, app_token: str
    ) -> None:
        """Fetch an achievement's details and persist it as an entry."""
        detail = self.get_achievement_detail(app_token, achievement_id)
        icon = self.get_achievement_icon(app_token, achievement_id)

        realm_slug = character["realm"]["slug"]
        name = character["name"]
        url = (
            f"https://worldofwarcraft.blizzard.com/en-{self.get_config('region')}"
            f"/character/{self.get_config('region')}/{realm_slug}/{name}"
        )
        text = f"{detail['name']} --- {detail.get('description', '')}"
        utcdate = datetime.fromtimestamp(completed_ms / 1000, tz=timezone.utc)

        self.logger.info("%s, %s, %s", realm_slug, name, text)
        self.entry_store.add_entry(
            "gaming",
            self._achievement_entry_id(achievement_id),
            text,
            "blizzard_wow",
            utcdate,
            url=url,
            image=icon,
            fulldata_json=detail,
        )

    def process_character(
        self, character: dict, user_token: str, app_token: str
    ) -> None:
        """Log every not-yet-seen completed achievement for one character."""
        realm_slug = character["realm"]["slug"]
        name = character["name"]
        self.logger.info("%s!%s L%d", realm_slug, name, character.get("level", 0))

        try:
            achievements = self.get_character_achievements(user_token, character)
        except WowCharacterNotFound:
            self.logger.warning("404 getting %s on %s", name, realm_slug)
            return

        for entry in achievements:
            try:
                self._process_achievement_entry(entry, character, app_token)
            except WowAchievementNotFound as e:
                self.logger.warning(str(e))
            except Exception as e:
                # One achievement with an unexpected shape (e.g. a schema
                # surprise from an API this importer can't fully verify
                # without live credentials) shouldn't stop the rest of this
                # character's achievements — or the account's other
                # characters — from being processed.
                self.logger.error(
                    "Failed to process an achievement for %s on %s: %s",
                    name,
                    realm_slug,
                    e,
                )

    def _process_achievement_entry(
        self, entry: dict, character: dict, app_token: str
    ) -> None:
        """Log a single achievements-summary entry, if new and completed."""
        achievement_id = entry["achievement"]["id"]
        completed_ms = entry.get("completed_timestamp")
        if completed_ms is None:
            return

        entry_id = self._achievement_entry_id(achievement_id)
        if self.entry_store.get_by_id("gaming", entry_id):
            return

        self.log_achievement(achievement_id, completed_ms, character, app_token)

    def run(self) -> None:
        """Import completed achievements for every character on the account."""
        user_token = self.authenticate_user()["access_token"]
        app_token = self.fetch_app_token()

        characters = self.get_account_characters(user_token)
        for character in characters:
            try:
                self.process_character(character, user_token, app_token)
            except Exception as e:
                # A transient API failure (or an unexpected response shape
                # this importer can't fully verify without live credentials)
                # for one character shouldn't stop the rest of the account's
                # characters from being processed.
                self.logger.error(
                    "Failed to process character %s: %s",
                    character.get("name", "<unknown>"),
                    e,
                )


def main():
    """Entry point for CLI."""
    return WowImporter.main()


if __name__ == "__main__":
    exit(main())
