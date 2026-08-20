"""Tests for Guild Wars 2 achievements importer."""

from unittest.mock import MagicMock, patch

from guildwars2api.base import GuildWars2APIError

from lifestream.importers.gw2 import GW2Importer


class TestGW2Importer:
    def _make_importer(self):
        imp = GW2Importer()
        imp._args = imp.parse_args([])
        imp._entry_store = MagicMock()
        imp.get_config = MagicMock(return_value="test-api-key")
        return imp

    def test_validate_config_requires_apikey(self):
        imp = GW2Importer()
        imp.get_config = MagicMock(return_value=None)
        assert imp.validate_config() is False

    def test_run_adds_entry_for_completed_achievement(self):
        """A completed achievement with matching info is stored as an entry."""
        imp = self._make_importer()

        api = MagicMock()
        api.account_achievements.get.return_value = [{"id": 1, "done": True}]
        api.achievements.get.return_value = [
            {
                "id": 1,
                "name": "First Steps",
                "requirement": "Do a thing",
                "icon": "x.png",
            }
        ]

        with (
            patch("lifestream.importers.gw2.GuildWars2API", return_value=api),
            patch("lifestream.importers.gw2._get_categories", return_value=[]),
        ):
            imp.run()

        imp._entry_store.add_entry.assert_called_once()
        args = imp._entry_store.add_entry.call_args.args
        assert args[0] == "achievement"
        assert args[1] == 1
        assert "First Steps" in args[2]
        assert args[3] == "Guild Wars 2"

    def test_run_skips_achievements_without_fetched_info(self):
        """An achievement id present in the progress list but never resolved is skipped."""
        imp = self._make_importer()

        api = MagicMock()
        api.account_achievements.get.return_value = [{"id": 1, "done": True}]
        api.achievements.get.return_value = []

        with (
            patch("lifestream.importers.gw2.GuildWars2API", return_value=api),
            patch("lifestream.importers.gw2._get_categories", return_value=[]),
        ):
            imp.run()

        imp._entry_store.add_entry.assert_not_called()

    def test_run_backs_off_on_api_error_without_raising(self):
        """A GuildWars2APIError is logged and the run ends cleanly instead of crashing."""
        imp = self._make_importer()

        api = MagicMock()
        api.account_achievements.get.side_effect = GuildWars2APIError("rate limited")

        with (
            patch("lifestream.importers.gw2.GuildWars2API", return_value=api),
            patch("lifestream.core.cache.get_redis_connection") as mock_redis,
        ):
            mock_redis.return_value.get.return_value = None
            imp.run()  # should not raise

        imp._entry_store.add_entry.assert_not_called()
