"""Tests for the Planetside 2 importer."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from lifestream.importers.base import ConfigurationError
from lifestream.importers.planetside import PlanetsideImporter

CHARACTER_RESPONSE = {
    "character_list": [
        {
            "character_id": "12345",
            "battle_rank": {"value": "50"},
            "faction": {"code_tag": "VS"},
            "name": {"first": "TestChar"},
        }
    ]
}

RANK_RESPONSE = {
    "experience_rank_list": [
        {
            "vs": {"title": {"en": "Elite"}},
            "vs_image_path": "/files/ps2/images/static/1.png",
        }
    ]
}

ACHIEVEMENTS_RESPONSE = {
    "characters_achievement_list": [
        {
            "finish": "1",
            "finish_date": "1700000000",
            "achievement_id_join_achievement": {
                "name": {"en": "First Kill"},
                "image_path": "/files/ps2/images/static/2.png",
            },
        },
        {
            "finish": "0",
            "finish_date": "0",
            "achievement_id_join_achievement": {
                "name": {"en": "Unfinished"},
                "image_path": "/files/ps2/images/static/3.png",
            },
        },
    ]
}


def _fake_get(url, params=None, timeout=None):
    response = MagicMock()
    if url.endswith("/character/"):
        response.json.return_value = CHARACTER_RESPONSE
    elif url.endswith("/experience_rank"):
        response.json.return_value = RANK_RESPONSE
    elif url.endswith("/characters_achievement/"):
        response.json.return_value = ACHIEVEMENTS_RESPONSE
    return response


class TestPlanetsideImporter:
    def _make_importer(self, characters="TestChar", service_key=None):
        imp = PlanetsideImporter()
        imp._args = imp.parse_args([])
        imp._entry_store = MagicMock()
        imp.get_config = MagicMock(
            side_effect=lambda k, fallback=None: {
                "characters": characters,
                "service_key": service_key,
            }.get(k, fallback)
        )
        return imp

    def test_validate_config_fails_when_characters_missing(self):
        imp = PlanetsideImporter()
        imp.get_config = MagicMock(return_value=None)
        with pytest.raises(ConfigurationError):
            imp.validate_config()

    def test_validate_config_passes_when_characters_present(self):
        imp = PlanetsideImporter()
        imp.get_config = MagicMock(return_value="set")
        assert imp.validate_config() is True

    def test_run_adds_rank_and_achievement_entries(self):
        imp = self._make_importer()

        with patch(
            "lifestream.importers.planetside.requests.get", side_effect=_fake_get
        ):
            imp.run()

        assert imp._entry_store.add_entry.call_count == 2

        rank_call, achievement_call = imp._entry_store.add_entry.call_args_list
        rank_args = rank_call.args
        assert rank_args[0] == "gaming"
        assert "TestChar achieved the rank Elite" in rank_args[2]
        assert rank_args[3] == "Planetside 2"

        achievement_args = achievement_call.args
        assert achievement_args[0] == "gaming"
        assert "TestChar earnt First Kill" in achievement_args[2]
        assert achievement_args[3] == "PS2 Achievement"

    def test_achievement_date_is_converted_from_unix_epoch(self):
        """finish_date is a Unix-epoch string; the `lifestream` table's
        date_created column is a DATETIME, so it must be converted rather
        than passed through as-is."""
        imp = self._make_importer()

        with patch(
            "lifestream.importers.planetside.requests.get", side_effect=_fake_get
        ):
            imp.run()

        _, achievement_call = imp._entry_store.add_entry.call_args_list
        assert achievement_call.args[4] == datetime.fromtimestamp(1700000000, tz=UTC)

    def test_achievement_text_uses_the_apis_canonical_name(self):
        """The API's own capitalization of the name is used for achievement
        text/hashing, not however it happens to be spelled in config -
        matching the legacy importer, which reassigned character_name to the
        API's name right after fetching the profile."""
        imp = self._make_importer(characters="testchar")

        with patch(
            "lifestream.importers.planetside.requests.get", side_effect=_fake_get
        ):
            imp.run()

        _, achievement_call = imp._entry_store.add_entry.call_args_list
        assert achievement_call.args[2].startswith("TestChar earnt")

    def test_run_skips_unfinished_achievements(self):
        imp = self._make_importer()

        with patch(
            "lifestream.importers.planetside.requests.get", side_effect=_fake_get
        ):
            imp.run()

        texts = [c.args[2] for c in imp._entry_store.add_entry.call_args_list]
        assert not any("Unfinished" in t for t in texts)

    def test_run_processes_every_configured_character(self):
        imp = self._make_importer(characters="Alice,Bob")

        with patch(
            "lifestream.importers.planetside.requests.get", side_effect=_fake_get
        ) as mock_get:
            imp.run()

        # 2 requests (character, achievements) + 1 (experience_rank) per character.
        assert mock_get.call_count == 6
        assert imp._entry_store.add_entry.call_count == 4

    def test_run_omits_service_key_prefix_when_unconfigured(self):
        imp = self._make_importer(service_key=None)

        with patch(
            "lifestream.importers.planetside.requests.get", side_effect=_fake_get
        ) as mock_get:
            imp.run()

        called_url = mock_get.call_args_list[0].args[0]
        assert "census.daybreakgames.com//get/ps2:v2" in called_url

    def test_run_includes_service_key_prefix_when_configured(self):
        imp = self._make_importer(service_key="mykey")

        with patch(
            "lifestream.importers.planetside.requests.get", side_effect=_fake_get
        ) as mock_get:
            imp.run()

        called_url = mock_get.call_args_list[0].args[0]
        assert "census.daybreakgames.com/s:mykey/get/ps2:v2" in called_url

    def test_run_reraises_error_after_logging(self):
        """An API failure is logged, then re-raised so jobs.run_import's
        failure-notification path still sees the job as failed (matching the
        legacy script's sys.exit(1)) instead of the run silently "succeeding".
        """
        imp = self._make_importer()
        imp.logger = MagicMock()

        with (
            patch(
                "lifestream.importers.planetside.requests.get",
                side_effect=OSError("census is down"),
            ),
            patch("lifestream.core.cache.get_redis_connection") as mock_redis,
        ):
            mock_redis.return_value.get.return_value = None
            with pytest.raises(OSError):
                imp.run()

        imp._entry_store.add_entry.assert_not_called()
        imp.logger.error.assert_called_once()
        assert "census is down" in str(imp.logger.error.call_args.args[1])

    def test_run_logs_at_info_level_when_error_already_warned_recently(self):
        """The backoff-suppressed second failure still re-raises, just logged quieter."""
        imp = self._make_importer()
        imp.logger = MagicMock()

        with (
            patch(
                "lifestream.importers.planetside.requests.get",
                side_effect=OSError("census is down"),
            ),
            patch("lifestream.core.cache.get_redis_connection") as mock_redis,
        ):
            mock_redis.return_value.get.return_value = "1"
            mock_redis.return_value.ttl.return_value = 3600
            with pytest.raises(OSError):
                imp.run()

        imp.logger.error.assert_not_called()
        backoff_call = imp.logger.info.call_args_list[-1]
        assert backoff_call.args[0] == (
            "Error importing Planetside data: %s (already warned %s ago)"
        )
        assert "census is down" in str(backoff_call.args[1])

        imp.logger.error.assert_not_called()
        imp.logger.info.assert_any_call(
            "Error importing Planetside data: %s (already warned %s ago)",
            imp.logger.info.call_args_list[-1].args[1],
            imp.logger.info.call_args_list[-1].args[2],
        )
