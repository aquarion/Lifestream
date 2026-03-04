"""Steam achievements importer for Lifestream."""

import argparse
import hashlib
from datetime import datetime

import pytz
import requests

from lifestream.importers.base import BaseImporter


class SteamImporter(BaseImporter):
    """Import achievements from Steam."""

    name = "steam"
    description = "Import achievements from Steam"
    config_section = "steam"

    STEAMTIME = pytz.timezone("US/Pacific")

    def add_arguments(self, parser: argparse.ArgumentParser) -> None:
        """Add Steam-specific arguments."""
        parser.add_argument(
            "--catchup",
            required=False,
            help="Get all achievements, not just last fortnight",
            default=False,
            action="store_true",
        )

    def validate_config(self) -> bool:
        """Ensure Steam credentials are configured."""
        if not self.get_config("username"):
            self.logger.error("No Steam username in config")
            return False
        return True

    def run(self) -> None:  # noqa: C901
        """Import achievements from Steam."""
        # Import here to avoid circular imports
        from lifestream.core.steam_api import SteamAPI

        user = self.get_config("username")
        steam_cxn = SteamAPI()

        if self.args.catchup:
            self.logger.info("CATCHUP MODE: Fetching all achievements.")
            games = steam_cxn.get_owned_games(include_appinfo=True)
        else:
            self.logger.info("NORMAL MODE: Fetching only recent achievements.")
            games = steam_cxn.get_recently_played_games(count=10)

        game_list = games["response"].get("games", [])
        self.logger.info(f"Found {len(game_list)} games to check for achievements.")

        for game in game_list:
            appid = game["appid"]
            name = game["name"]
            playtime_2weeks = game.get("playtime_2weeks", 0)
            playtime_forever = game["playtime_forever"]

            text = f"Played {name}: {playtime_2weeks} mins in last 2 weeks, {playtime_forever} mins total."
            self.logger.info(text)

            try:
                player_achievements = steam_cxn.get_player_achievements(appid)
            except requests.HTTPError as e:
                self.logger.warning(
                    f"Error fetching achievements for {name} ({appid}): {e}"
                )
                continue

            unsorted_game_achievements = steam_cxn.get_game_achievements(appid)

            game_achievements = {}
            if (
                "availableGameStats" not in unsorted_game_achievements["game"]
                or "achievements"
                not in unsorted_game_achievements["game"]["availableGameStats"]
            ):
                self.logger.info(f"   + No achievements found for {name} ({appid}).")
                continue

            for achievement in unsorted_game_achievements["game"]["availableGameStats"][
                "achievements"
            ]:
                game_achievements[achievement["name"]] = achievement

            if (
                "playerstats" in player_achievements
                and "achievements" in player_achievements["playerstats"]
            ):
                for player_achievement in player_achievements["playerstats"][
                    "achievements"
                ]:
                    if player_achievement["achieved"] == 1:
                        ach_id = player_achievement["apiname"]
                        game_achievement = game_achievements.get(ach_id, {})
                        ach_name = game_achievement.get(
                            "displayName", "Unknown Achievement"
                        )

                        message = f"{name} &ndash; {ach_name}"

                        achieved_date = datetime.fromtimestamp(
                            player_achievement["unlocktime"]
                        )

                        self.logger.info(message)

                        open_image = game_achievement.get("icon", None)

                        id_hash = hashlib.md5()
                        id_hash.update(f"{appid}-{ach_id}".encode("utf-8"))

                        entry = self.entry_store.get_by_title("achievement", message)
                        if entry and not entry["systemid"] == id_hash.hexdigest():
                            self.logger.info(
                                "           + Achievement already in Lifestream, deleting."
                            )
                            self.logger.info(
                                f"             + Entry ID: {entry['title']}"
                            )
                            self.entry_store.delete_entry(
                                entry["type"], entry["systemid"]
                            )
                        else:
                            self.logger.info(
                                "           + Adding Achievement to entry_store."
                            )

                        stats_page = f"https://steamcommunity.com/id/{user}/stats/{appid}/?tab=achievements"

                        self.entry_store.add_entry(
                            "achievement",
                            id_hash.hexdigest(),
                            message,
                            "steam",
                            achieved_date,
                            url=stats_page,
                            image=open_image,
                        )


def main():
    """Entry point for CLI."""
    return SteamImporter.main()


if __name__ == "__main__":
    exit(main())
