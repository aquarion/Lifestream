"""Foursquare importer for Lifestream."""

from datetime import datetime, timezone

import requests

from lifestream.core import code_fetcher
from lifestream.importers.base import OAuthImporter

AUTHORIZE_URL = "https://foursquare.com/oauth2/authenticate"
ACCESS_TOKEN_URL = "https://foursquare.com/oauth2/access_token"
CHECKINS_URL = "https://api.foursquare.com/v2/users/self/checkins"
API_VERSION = "20180226"

# Foursquare's app registration requires a fixed redirect_uri; used only when
# the webserver's OAuth catcher (code_fetcher) isn't configured/available.
FALLBACK_REDIRECT_URI = "https://github.com/aquarion/lifestream"


class FoursquareImporter(OAuthImporter):
    """Import checkins from Foursquare."""

    name = "foursquare"
    description = "Import checkins from Foursquare"
    config_section = "foursquare"
    oauth_filename = "foursquare.oauth"

    def validate_config(self) -> bool:
        """Ensure Foursquare app credentials are configured."""
        missing = [
            k for k in ("client_id", "secret", "username") if not self.get_config(k)
        ]
        if missing:
            self.logger.error(f"Missing Foursquare config keys: {', '.join(missing)}")
            return False
        return True

    def _redirect_uri(self) -> tuple[str, bool]:
        """Return (redirect_uri, use_code_fetcher)."""
        try:
            code_fetcher.are_we_working()
            return code_fetcher.get_url(), True
        except code_fetcher.WeSayNotToday:
            return FALLBACK_REDIRECT_URI, False

    def authenticate(self) -> str:
        """
        Run Foursquare's OAuth 2.0 flow (via the webserver's OAuth catcher, or
        a manual code paste) and return the access token, refreshing/persisting
        it as needed.
        """
        client_id = self.get_config("client_id")
        client_secret = self.get_config("secret")

        access_token = None if self.args.reauth else self.load_oauth_token()
        if access_token:
            return access_token

        redirect_uri, use_code_fetcher = self._redirect_uri()

        # intentional: user must visit this URL to complete OAuth; contains no
        # secret, only the public client_id and redirect_uri
        auth_url = (
            f"{AUTHORIZE_URL}?client_id={client_id}&response_type=code"
            f"&redirect_uri={redirect_uri}"
        )
        print("Go to the following link in your browser:")
        print(auth_url)  # codeql[py/clear-text-logging-sensitive-data]
        print()

        if use_code_fetcher:
            oauth_redirect = code_fetcher.get_code("code")
            auth_code = oauth_redirect["code"][0]
        else:
            print("If you configure [webserver], this is a lot easier.")
            auth_code = input("Paste the ?code= value from the redirected URL: ")

        token_response = requests.get(
            ACCESS_TOKEN_URL,
            params={
                "client_id": client_id,
                "client_secret": client_secret,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code": auth_code,
            },
            timeout=30,
        )
        token_response.raise_for_status()
        access_token = token_response.json()["access_token"]

        self.save_oauth_token(access_token)
        return access_token

    @staticmethod
    def _checkin_source(checkin: dict) -> str:
        return "Foursquare-Mayor" if checkin.get("isMayor") else "Foursquare"

    @staticmethod
    def _checkin_message_and_image(checkin: dict) -> tuple[str, str]:
        venue = checkin.get("venue")
        if not venue:
            return checkin["location"]["name"], ""

        image = ""
        for category in venue.get("categories", []):
            if category.get("primary"):
                image = category["icon"]["prefix"] + "64.png"
                break
        return venue["name"], image

    def process_checkin(self, checkin: dict, username: str) -> None:
        """Persist a single Foursquare checkin as an entry (and, if it has a
        venue, a location point)."""
        source = self._checkin_source(checkin)
        message, image = self._checkin_message_and_image(checkin)

        utctime = datetime.fromtimestamp(checkin["createdAt"], tz=timezone.utc)
        utcdate = utctime.strftime("%Y-%m-%d %H:%M")
        checkin_id = checkin["id"]
        url = f"http://www.foursquare.com/{username}/checkin/{checkin_id}"

        self.logger.info("Checkin %s@%s", utcdate, message)
        self.entry_store.add_entry(
            "location",
            checkin_id,
            message,
            source,
            utcdate,
            url=url,
            image=image,
            fulldata_json=checkin,
        )

        venue = checkin.get("venue")
        if venue:
            coordinates = venue["location"]
            self.entry_store.add_location(
                utctime,
                "foursquare",
                coordinates["lat"],
                coordinates["lng"],
                message,
                image,
            )

    def run(self) -> None:
        """Import checkins for the configured Foursquare user."""
        username = self.get_config("username")
        access_token = self.authenticate()

        response = requests.get(
            CHECKINS_URL,
            params={"v": API_VERSION, "oauth_token": access_token},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        checkins = data["response"]["checkins"]["items"]
        for checkin in checkins:
            self.process_checkin(checkin, username)


def main():
    """Entry point for CLI."""
    return FoursquareImporter.main()


if __name__ == "__main__":
    exit(main())
