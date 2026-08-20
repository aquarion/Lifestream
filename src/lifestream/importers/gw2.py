"""Guild Wars 2 achievements importer for Lifestream."""

from datetime import datetime

import requests
from guildwars2api.base import GuildWars2APIError
from guildwars2api.v2 import GuildWars2API

from lifestream.core import check_and_set_backoff, file_cache, niceTimeDelta
from lifestream.importers.base import BaseImporter


@file_cache("gw2.categories", 86400)
def _get_categories():
    list_response = requests.get(
        "https://api.guildwars2.com/v2/achievements/categories/", timeout=30
    )
    list_response.raise_for_status()
    category_list = list_response.json()

    category_fetch = []

    step = 200
    for i in range(0, len(category_list), step):
        category_params = {"ids": ",".join(str(x) for x in category_list[i : i + step])}
        category_response = requests.get(
            "https://api.guildwars2.com/v2/achievements/categories",
            params=category_params,
            timeout=30,
        )
        category_response.raise_for_status()
        category_fetch += category_response.json()

    return category_fetch


def _get_icon(achievement):
    if "icon" in achievement["info"]:
        return achievement["info"]["icon"]
    if "category" in achievement:
        return achievement["category"]["icon"]
    return "https://wiki.guildwars2.com/images/d/d9/Retired_Achievements.png"


class GW2Importer(BaseImporter):
    """Import completed achievements from Guild Wars 2."""

    name = "gw2"
    description = "Import completed achievements from Guild Wars 2"
    config_section = "guildwars2"

    def validate_config(self) -> bool:
        """Ensure a Guild Wars 2 API key is configured."""
        if not self.get_config("apikey"):
            self.logger.error("No Guild Wars 2 API key in config")
            return False
        return True

    def _get_all_my_achievements(self, api):
        my_achievements = api.account_achievements.get()

        fetch_list = []
        achievements_library = {}

        for achievement in my_achievements:
            if achievement["done"]:
                ident = achievement["id"]
                fetch_list.append(ident)
                achievements_library[ident] = {"progress": achievement}

        self.logger.debug("Fetch list is %d long", len(fetch_list))

        ach_pagesize = 100
        list_size = len(fetch_list)

        for ach_index in range(0, list_size, ach_pagesize):
            fetch_chunk = fetch_list[ach_index : ach_index + ach_pagesize]
            self.logger.debug(
                "Fetching achievement %d to %d of %d",
                ach_index,
                ach_index + ach_pagesize,
                len(fetch_chunk),
            )

            response = api.achievements.get(ids=fetch_chunk)

            for achievement in response:
                ident = achievement["id"]
                achievements_library[ident]["info"] = achievement

        return achievements_library

    def run(self) -> None:
        """Fetch completed achievements and add any new ones."""
        api = GuildWars2API(
            user_agent="Lifestream <nicholas@istic.net>",
            api_key=self.get_config("apikey"),
        )

        try:
            achievements_library = self._get_all_my_achievements(api)
        except GuildWars2APIError as e:
            ttl = check_and_set_backoff("gw2:api_error:warning_sent")
            if ttl:
                self.logger.info(
                    "Error fetching achievements: %s (already warned %s ago)",
                    e,
                    niceTimeDelta(ttl),
                )
            else:
                self.logger.error("Error fetching achievements: %s", e)
            raise

        for category in _get_categories():
            for achievement_id in category["achievements"]:
                if achievement_id in achievements_library:
                    achievements_library[achievement_id]["category"] = category

        for ident, achievement in achievements_library.items():
            if "info" not in achievement:
                continue

            icon = _get_icon(achievement)
            if not icon:
                self.logger.warning("%s has no icon", achievement["info"]["name"])

            text = f"{achievement['info']['name']} &ndash; {achievement['info']['requirement']}"
            self.logger.info(text)
            self.entry_store.add_entry(
                "achievement", ident, text, "Guild Wars 2", datetime.now(), image=icon
            )


def main():
    """Entry point for CLI."""
    return GW2Importer.main()


if __name__ == "__main__":
    exit(main())
