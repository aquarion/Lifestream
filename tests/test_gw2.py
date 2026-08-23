"""Tests for Guild Wars 2 achievements importer."""

from unittest.mock import MagicMock, patch

import pytest
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

    def test_get_categories_sends_ids_as_query_params(self):
        """Regression test for a bug where achievement category ids were sent
        via data= on a GET request, which the GW2 API silently ignores."""
        from lifestream.importers.gw2 import _get_categories

        list_response = MagicMock()
        list_response.json.return_value = [1, 2, 3]
        chunk_response = MagicMock()
        chunk_response.json.return_value = [{"id": 1, "achievements": []}]

        mock_redis = MagicMock()
        mock_redis.get.return_value = None

        with (
            patch(
                "lifestream.importers.gw2.requests.get",
                side_effect=[list_response, chunk_response],
            ) as mock_get,
            patch(
                "lifestream.core.cache.get_redis_connection", return_value=mock_redis
            ),
        ):
            _get_categories()

        chunk_call = mock_get.call_args_list[1]
        assert chunk_call.kwargs["params"] == {"ids": "1,2,3"}
        assert "data" not in chunk_call.kwargs

    def test_run_reraises_api_error_after_logging(self):
        """A GuildWars2APIError is logged, then re-raised so jobs.run_import's
        failure-notification path still sees the job as failed (matching the
        legacy script's sys.exit(1)) instead of the run silently "succeeding".
        """
        imp = self._make_importer()

        api = MagicMock()
        api.account_achievements.get.side_effect = GuildWars2APIError("rate limited")

        with (
            patch("lifestream.importers.gw2.GuildWars2API", return_value=api),
            patch("lifestream.core.cache.get_redis_connection") as mock_redis,
        ):
            mock_redis.return_value.get.return_value = None
            with pytest.raises(GuildWars2APIError):
                imp.run()

        imp._entry_store.add_entry.assert_not_called()

    def test_run_logs_at_info_level_when_error_already_warned_recently(self):
        """The backoff-suppressed second failure still re-raises, just logged quieter."""
        imp = self._make_importer()

        api = MagicMock()
        api.account_achievements.get.side_effect = GuildWars2APIError("rate limited")

        with (
            patch("lifestream.importers.gw2.GuildWars2API", return_value=api),
            patch("lifestream.core.cache.get_redis_connection") as mock_redis,
        ):
            mock_redis.return_value.get.return_value = "1"
            mock_redis.return_value.ttl.return_value = 3600
            with pytest.raises(GuildWars2APIError):
                imp.run()
