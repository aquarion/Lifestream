"""Tests for Steam achievements importer."""

from datetime import timezone
from unittest.mock import MagicMock, patch

import requests

from lifestream.importers.steam import SteamImporter


class TestSteamImporter:
    def _make_importer(self):
        imp = SteamImporter()
        imp._args = imp.parse_args([])
        imp._entry_store = MagicMock()
        imp.get_config = MagicMock(return_value="testuser")
        return imp

    def _make_steam_api(self, unlocktime=1_700_000_000, achieved_name="an_achievement"):
        steam_cxn = MagicMock()
        steam_cxn.get_recently_played_games.return_value = {
            "response": {
                "games": [{"appid": 1, "name": "Game One", "playtime_forever": 60}]
            }
        }
        steam_cxn.get_player_achievements.return_value = {
            "playerstats": {
                "achievements": [
                    {
                        "apiname": achieved_name,
                        "achieved": 1,
                        "unlocktime": unlocktime,
                    }
                ]
            }
        }
        steam_cxn.get_game_achievements.return_value = {
            "game": {
                "availableGameStats": {
                    "achievements": [
                        {"name": achieved_name, "displayName": "An Achievement"}
                    ]
                }
            }
        }
        return steam_cxn

    def test_run_stores_achievement_timestamp_as_utc(self):
        """The achievement unlock time is stored as a UTC-aware datetime, not local time."""
        imp = self._make_importer()
        steam_cxn = self._make_steam_api(unlocktime=1_700_000_000)
        imp._entry_store.get_by_title.return_value = None

        with patch("lifestream.core.steam_api.SteamAPI", return_value=steam_cxn):
            imp.run()

        _, kwargs = imp._entry_store.add_entry.call_args
        achieved_date = imp._entry_store.add_entry.call_args.args[4]
        assert achieved_date.tzinfo is not None
        assert achieved_date.utcoffset().total_seconds() == 0
        assert achieved_date.astimezone(timezone.utc) == achieved_date

    def test_run_deletes_stale_entry_with_different_systemid(self):
        """An existing entry with the same title but a different systemid gets deleted."""
        imp = self._make_importer()
        steam_cxn = self._make_steam_api()
        imp._entry_store.get_by_title.return_value = {
            "type": "achievement",
            "systemid": "stale-id",
            "title": "Game One – An Achievement",
        }

        with patch("lifestream.core.steam_api.SteamAPI", return_value=steam_cxn):
            imp.run()

        imp._entry_store.delete_entry.assert_called_once_with("achievement", "stale-id")

    def test_run_skips_game_on_http_error_and_continues(self):
        """An HTTPError fetching one game's achievements is logged and skipped, not fatal."""
        imp = self._make_importer()
        steam_cxn = MagicMock()
        steam_cxn.get_recently_played_games.return_value = {
            "response": {
                "games": [
                    {"appid": 1, "name": "Broken Game", "playtime_forever": 10},
                ]
            }
        }
        steam_cxn.get_player_achievements.side_effect = requests.HTTPError("503 error")

        with patch("lifestream.core.steam_api.SteamAPI", return_value=steam_cxn):
            imp.run()  # should not raise

        imp._entry_store.add_entry.assert_not_called()
