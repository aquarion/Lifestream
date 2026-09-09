"""Last.fm scrobble importer for Lifestream."""

import argparse
import hashlib
from datetime import datetime, timezone

import requests

from lifestream.importers.base import BaseImporter, ConfigurationError

API_URL = "https://ws.audioscrobbler.com/2.0/"
DEFAULT_LIMIT = 50


class LastfmImporter(BaseImporter):
    """Import recent Last.fm scrobbles via the official Last.fm Web API."""

    name = "lastfm"
    description = "Import recent Last.fm scrobbles"
    config_section = "lastfm"
    entry_type = "lastfm"
    source_name = "lastfm"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add Last.fm-specific arguments."""
        parser.add_argument(
            "--limit",
            type=int,
            default=DEFAULT_LIMIT,
            help="Number of recent scrobbles to fetch",
        )

    def validate_config(self) -> bool:
        """Ensure Last.fm credentials are configured."""
        missing = [k for k in ("username", "api_key") if not self.get_config(k)]
        if missing:
            self.logger.error(f"Missing Last.fm config keys: {', '.join(missing)}")
            return False
        return True

    @staticmethod
    def _track_id(track: dict) -> str:
        # Last.fm doesn't hand out a per-scrobble id, so hash the fields that
        # tell one scrobble apart from a repeat play of the same track.
        artist = track["artist"]["#text"]
        name = track["name"]
        uts = track["date"]["uts"]
        return hashlib.md5(f"{artist}-{name}-{uts}".encode()).hexdigest()

    @staticmethod
    def _track_image(track: dict) -> str:
        images = {
            image.get("size"): image.get("#text", "")
            for image in track.get("image", [])
        }
        for size in ("extralarge", "large", "medium", "small"):
            if images.get(size):
                return images[size]
        return ""

    def _process_track(self, track: dict) -> None:
        if "date" not in track:
            # The currently-playing track carries no timestamp — nothing to
            # log until it's actually finished scrobbling.
            return

        artist = track["artist"]["#text"]
        name = track["name"]
        title = f"{artist} – {name}"
        utcdate = datetime.fromtimestamp(int(track["date"]["uts"]), tz=timezone.utc)

        self.logger.info(title)
        self.entry_store.add_entry(
            self.entry_type,
            self._track_id(track),
            title,
            self.source_name,
            utcdate,
            url=track.get("url", ""),
            image=self._track_image(track),
            fulldata_json=track,
        )

    def run(self) -> None:
        """Import recent Last.fm scrobbles."""
        username = self.get_config("username")
        api_key = self.get_config("api_key")

        response = requests.get(
            API_URL,
            params={
                "method": "user.getrecenttracks",
                "user": username,
                "api_key": api_key,
                "format": "json",
                "limit": self.args.limit,
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            raise ConfigurationError(
                f"Last.fm API error {data['error']}: "
                f"{data.get('message', 'unknown error')}"
            )

        tracks = data.get("recenttracks", {}).get("track", [])
        # A single-result response comes back as a bare dict, not a
        # one-element list.
        if isinstance(tracks, dict):
            tracks = [tracks]

        for track in tracks:
            self._process_track(track)


def main():
    """Entry point for CLI."""
    return LastfmImporter.main()


if __name__ == "__main__":
    exit(main())
