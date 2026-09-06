"""Steam badges importer for Lifestream.

Scrapes the Steam Community badges page directly via requests + BeautifulSoup
instead of a full browser: the badge markup — including each badge's real
icon URL, which sits in a data-delayed-image attribute rather than the
lazy-load placeholder <img src> — is already present in the plain
server-rendered HTML, so no JS execution (and no Selenium/webdriver
dependency) is needed.
"""

import hashlib
from datetime import datetime

import bs4
import pytz
import requests

from lifestream.importers.base import BaseImporter

BADGES_URL = "https://steamcommunity.com/id/{username}/badges"
STEAM_TIMEZONE = pytz.timezone("US/Pacific")
UNLOCKED_PREFIX = "Unlocked "


class SteamBadgesImporter(BaseImporter):
    """Import Steam badge unlocks."""

    name = "steambadges"
    description = "Import Steam badge unlocks"
    config_section = "steam"

    def validate_config(self) -> bool:
        """Ensure Steam credentials are configured."""
        if not self.get_config("username"):
            self.logger.error("Missing Steam config key: username")
            return False
        return True

    def fetch_badges_page(self, username: str) -> str:
        """Fetch the raw badges page HTML for a Steam Community username."""
        response = requests.get(
            BADGES_URL.format(username=username),
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )
        response.raise_for_status()
        return response.text

    @staticmethod
    def _parse_unlocked_date(text: str) -> datetime:
        """Parse a badge's "Unlocked ..." timestamp (prefix already
        stripped) into a UTC datetime. Steam omits the year for badges
        unlocked in the current year."""
        text = text.strip()
        if text.startswith(UNLOCKED_PREFIX):
            text = text[len(UNLOCKED_PREFIX) :]
        try:
            parsed = datetime.strptime(text, "%b %d, %Y @ %I:%M%p")
        except ValueError:
            # datetime.now().year is the system clock's year, not Pacific
            # time's (STEAM_TIMEZONE) — right at the new year boundary this
            # could misattribute a Dec 31 badge to the wrong year. Narrow
            # window, low consequence (only affects display; the entry id
            # is keyed on the raw unlocked_text, not this parsed year).
            parsed = datetime.strptime(text, "%b %d @ %I:%M%p").replace(
                year=datetime.now().year
            )
        localized = STEAM_TIMEZONE.localize(parsed)
        return localized.astimezone(pytz.utc)

    def parse_badges(self, html: str, fallback_url: str) -> list[dict]:
        """Parse each badge row out of a badges page into a plain dict."""
        soup = bs4.BeautifulSoup(html, "html.parser")
        badges = []

        for row in soup.select("div.badge_row"):
            title_tag = row.select_one(".badge_info_title")
            unlocked_tag = row.select_one(".badge_info_unlocked")
            if not title_tag or not unlocked_tag:
                # Badges still in progress (not yet unlocked) have no
                # unlocked-date element — nothing to log for those.
                continue

            image_tag = row.select_one(".badge_info_image img")
            image = image_tag.get("data-delayed-image", "") if image_tag else ""

            link_tag = row.select_one("a.badge_row_overlay")
            url = (
                link_tag["href"] if link_tag and link_tag.get("href") else fallback_url
            )

            badges.append(
                {
                    "title": title_tag.text.strip(),
                    "unlocked_text": unlocked_tag.text.strip(),
                    "image": image,
                    "url": url,
                }
            )

        return badges

    @staticmethod
    def _badge_entry_id(title: str, unlocked_text: str) -> str:
        # Includes the unlock timestamp, not just the title: some badges
        # (e.g. "Years of Service") share the same title across repeated
        # unlocks, and a title-only id would collapse them into one entry.
        return hashlib.md5(f"{title}-{unlocked_text}".encode("utf8")).hexdigest()

    def process_badge(self, badge: dict) -> None:
        """Persist a single parsed badge as an entry."""
        try:
            utcdate = self._parse_unlocked_date(badge["unlocked_text"])
        except ValueError:
            self.logger.warning(
                "Couldn't parse unlock date %r for badge %r, skipping",
                badge["unlocked_text"],
                badge["title"],
            )
            return

        self.logger.info(badge["title"])
        self.entry_store.add_entry(
            "badge",
            self._badge_entry_id(badge["title"], badge["unlocked_text"]),
            badge["title"],
            "steam",
            utcdate,
            url=badge["url"],
            image=badge["image"],
        )

    def run(self) -> None:
        """Import badge unlocks for the configured Steam username."""
        username = self.get_config("username")
        url = BADGES_URL.format(username=username)

        html = self.fetch_badges_page(username)
        for badge in self.parse_badges(html, fallback_url=url):
            self.process_badge(badge)


def main():
    """Entry point for CLI."""
    return SteamBadgesImporter.main()


if __name__ == "__main__":
    exit(main())
