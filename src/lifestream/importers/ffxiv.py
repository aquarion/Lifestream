"""Final Fantasy XIV Lodestone achievements importer for Lifestream."""

import argparse
import json
import math
import re
import sqlite3
from datetime import datetime
from urllib.parse import urlparse

import bs4
import requests

from lifestream.core import resolve_path
from lifestream.importers.base import BaseImporter, ConfigurationError

CHARACTER_SELECTORS = "datafiles/lodestone-css-selectors/profile/character.json"
ACHIEVEMENT_SELECTORS = "datafiles/lodestone-css-selectors/profile/achievements.json"


class Lodestone:
    """Scrapes character achievements from the FFXIV Lodestone."""

    base_url = "https://xivapi.com"

    def __init__(
        self, achievement_db_path: str, max_pages: int, all_achievements: bool
    ) -> None:
        self.achievement_db = sqlite3.connect(achievement_db_path)
        self.max_pages = max_pages
        self.all_achievements = all_achievements
        self.next = False

    def get_character_detail(self, character_id, section="", page=1, region="eu"):
        url = f"https://{region}.finalfantasyxiv.com/lodestone/character/{character_id}/{section}"
        params = {}
        if page > 1:
            params["page"] = page

        request = requests.get(url, params, timeout=30)
        return request.text

    def pull_value(self, selector_map, root):
        tags = root.select(selector_map["selector"])
        if not len(tags):
            raise ValueError(f"Selector not found: {selector_map['selector']}")

        if "regex" in selector_map:
            if "attribute" in selector_map:
                haystack = tags[0].get(selector_map["attribute"])
            else:
                haystack = tags[0].text.strip()

            re_result = re.findall(selector_map["regex"], haystack)
            if len(re_result) > 0:
                return re_result[0]
            raise ValueError(f"Regex not found: {selector_map['regex']}")

        if "multiple" in selector_map:
            return tags

        if "attribute" in selector_map:
            return tags[0].get(selector_map["attribute"])
        return tags[0]

    def _load_selector_map(self, relative_path: str) -> dict:
        path = resolve_path(relative_path)
        try:
            with open(path) as f:
                return json.load(f)
        except FileNotFoundError as e:
            raise ConfigurationError(
                f"Lodestone CSS selector file not found at {path} — is the "
                "datafiles/lodestone-css-selectors git submodule checked out? "
                "(git submodule update --init)"
            ) from e

    def get_character_info(self, character_id):
        html = self.get_character_detail(character_id)
        selector_map = self._load_selector_map(CHARACTER_SELECTORS)
        soup = bs4.BeautifulSoup(html, "html.parser")

        return {
            "Name": self.pull_value(selector_map["NAME"], soup).text,
            "Server": self.pull_value(selector_map["SERVER"], soup),
            "Title": self.pull_value(selector_map["TITLE"], soup).text,
        }

    def get_achievements(self, character_id):
        html = self.get_character_detail(character_id, "achievement")
        achievements = self.parse_achievements_page(html)
        page = 1
        while self.next:
            host = urlparse(self.next).hostname or ""
            if not (
                host == "finalfantasyxiv.com" or host.endswith(".finalfantasyxiv.com")
            ):
                raise ValueError(
                    f"Refusing to fetch next-page link off-site: {self.next}"
                )
            next_response = requests.get(self.next, timeout=30)
            next_response.raise_for_status()
            next_page_contents = next_response.text
            achievements += self.parse_achievements_page(next_page_contents)
            page += 1
            if page > self.max_pages and not self.all_achievements:
                break

        return achievements

    def icon_path(self, achievement_id):
        result = self.achievement_db.execute(
            "SELECT icon FROM achievements WHERE id = ?", (achievement_id,)
        )
        row = result.fetchone()
        if not row:
            return None
        icon_id = int(row[0])

        filename = f"{icon_id:06d}"
        foldername = f"{math.floor(icon_id / 1000) * 1000:06d}"

        return f"{foldername}/{filename}.png"

    def parse_achievements_page(self, html):
        selector_map = self._load_selector_map(ACHIEVEMENT_SELECTORS)
        soup = bs4.BeautifulSoup(html, "html.parser")

        root = self.pull_value(selector_map["ROOT"], soup)
        entries = self.pull_value(selector_map["ENTRY"]["ROOT"], root)

        self.next = self.pull_value(selector_map["LIST_NEXT_BUTTON"], root)
        if self.next == "javascript:void(0);":
            self.next = False

        achievements = []
        for entry in entries:
            achievement_id = self.pull_value(selector_map["ENTRY"]["ID"], entry)
            date_epoch = self.pull_value(selector_map["ENTRY"]["TIME"], entry)
            achievements.append(
                {
                    "Name": self.pull_value(selector_map["ENTRY"]["NAME"], entry)[1],
                    "ID": achievement_id,
                    "Icon": self.icon_path(achievement_id),
                    "Date": datetime.fromtimestamp(int(date_epoch)),
                }
            )

        return achievements


class FFXIVImporter(BaseImporter):
    """Import character achievements from the FFXIV Lodestone."""

    name = "ffxiv"
    description = "Import character achievements from the FFXIV Lodestone"
    config_section = "xivapi"

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add FFXIV-specific arguments."""
        parser.add_argument(
            "--all-achievements",
            required=False,
            help="Get all achievements, not just last few pages",
            default=False,
            action="store_true",
        )
        parser.add_argument(
            "--max-pages",
            required=False,
            type=int,
            help="Maximum number of pages to fetch",
            default=3,
        )

    def validate_config(self) -> bool:
        """Ensure xivapi credentials are configured."""
        missing = [
            k
            for k in ("apikey", "characters", "icon_base", "achievement_db")
            if not self.get_config(k)
        ]
        if missing:
            self.logger.error(f"Missing xivapi config keys: {', '.join(missing)}")
            return False
        return True

    def _update_achievements(self, lodestone: Lodestone, char_id: str) -> None:
        achievements = lodestone.get_achievements(char_id)
        character = lodestone.get_character_info(char_id)
        character_name = character["Name"]

        icon_base = self.get_config("icon_base")

        for achievement in achievements:
            self.logger.debug(
                "%s, %s, %s",
                achievement["Name"],
                achievement["Icon"],
                achievement["Date"],
            )

            message = f"FFXIV: {character_name} &ndash; {achievement['Name']}"
            url = (
                f"https://eu.finalfantasyxiv.com/lodestone/character/"
                f"{char_id}/achievement/detail/{achievement['ID']}/"
            )

            self.entry_store.add_entry(
                type="achievement",
                id=f"ffxiv-{char_id}-{achievement['ID']}",
                title=message,
                source="FFXIV",
                url=url,
                date=achievement["Date"],
                image=(
                    f"{icon_base}{achievement['Icon']}" if achievement["Icon"] else ""
                ),
                update=True,
            )

    def run(self) -> None:
        """Fetch and store new achievements for each configured character."""
        lodestone = Lodestone(
            self.get_config("achievement_db"),
            self.args.max_pages,
            self.args.all_achievements,
        )

        for character_id in self.get_config("characters").split(","):
            self._update_achievements(lodestone, character_id)


def main():
    """Entry point for CLI."""
    return FFXIVImporter.main()


if __name__ == "__main__":
    exit(main())
