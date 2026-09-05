"""Tests for the World of Warcraft importer."""

from unittest.mock import MagicMock, patch

import pytest

from lifestream.core import code_fetcher as real_code_fetcher
from lifestream.importers.base import ConfigurationError
from lifestream.importers.wow import (
    WowAchievementNotFound,
    WowCharacterNotFound,
    WowImporter,
)


class TestWowImporter:
    def _make_importer(self):
        imp = WowImporter()
        imp._args = imp.parse_args([])
        imp._entry_store = MagicMock()
        imp.get_config = MagicMock(
            side_effect=lambda k, fallback=None: {
                "key": "ckey",
                "secret": "csecret",
                "region": "eu",
            }.get(k, fallback)
        )
        return imp

    def test_validate_config_fails_when_keys_missing(self):
        imp = WowImporter()
        imp.get_config = MagicMock(return_value=None)
        assert imp.validate_config() is False

    def test_validate_config_passes_when_all_keys_present(self):
        imp = WowImporter()
        imp.get_config = MagicMock(return_value="set")
        assert imp.validate_config() is True

    def test_authenticate_user_uses_saved_token_without_reauth(self):
        imp = self._make_importer()
        imp.load_oauth_token = MagicMock(return_value={"access_token": "cached"})

        result = imp.authenticate_user()

        assert result == {"access_token": "cached"}

    def test_authenticate_user_runs_code_fetcher_flow_and_saves_token(self):
        imp = self._make_importer()
        imp.load_oauth_token = MagicMock(return_value=None)
        imp.save_oauth_token = MagicMock()

        token_response = MagicMock()
        token_response.json.return_value = {"access_token": "newtoken"}

        with (
            patch("lifestream.importers.wow.code_fetcher") as mock_cf,
            patch(
                "lifestream.importers.wow.requests.post",
                return_value=token_response,
            ) as mock_post,
            patch("builtins.print"),
        ):
            mock_cf.are_we_working.return_value = True
            mock_cf.get_url.return_value = "https://example.com/keyback/"
            mock_cf.get_code.return_value = {"code": ["abc123"]}

            result = imp.authenticate_user()

        assert result["access_token"] == "newtoken"
        assert "created_at" in result
        imp.save_oauth_token.assert_called_once_with(result)
        mock_post.assert_called_once()
        _, kwargs = mock_post.call_args
        assert kwargs["data"]["redirect_uri"] == "https://example.com/keyback/"
        assert kwargs["data"]["code"] == "abc123"

    def test_authenticate_user_raises_when_code_fetcher_unavailable(self):
        imp = self._make_importer()
        imp.load_oauth_token = MagicMock(return_value=None)

        with patch("lifestream.importers.wow.code_fetcher") as mock_cf:
            mock_cf.WeSayNotToday = real_code_fetcher.WeSayNotToday
            mock_cf.are_we_working.side_effect = real_code_fetcher.WeSayNotToday()

            with pytest.raises(ConfigurationError):
                imp.authenticate_user()

    def test_fetch_app_token_uses_client_credentials(self):
        imp = self._make_importer()

        with patch("lifestream.importers.wow.OAuth2Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.fetch_token.return_value = {"access_token": "apptoken"}
            mock_session_cls.return_value = mock_session

            result = imp.fetch_app_token()

        assert result == "apptoken"
        mock_session.fetch_token.assert_called_once_with(
            token_url="https://eu.battle.net/oauth/token",
            client_id="ckey",
            client_secret="csecret",
        )

    def test_get_account_characters_flattens_wow_accounts(self):
        imp = self._make_importer()
        response = MagicMock()
        response.json.return_value = {
            "wow_accounts": [
                {"characters": [{"name": "Alice"}, {"name": "Bob"}]},
                {"characters": [{"name": "Carl"}]},
            ]
        }

        with patch(
            "lifestream.importers.wow.requests.get", return_value=response
        ) as mock_get:
            result = imp.get_account_characters("usertok")

        assert [c["name"] for c in result] == ["Alice", "Bob", "Carl"]
        mock_get.assert_called_once_with(
            "https://eu.api.blizzard.com/profile/user/wow",
            params={
                "namespace": "profile-eu",
                "locale": "en_US",
                "access_token": "usertok",
            },
            timeout=30,
        )

    def test_get_character_achievements_returns_list(self):
        imp = self._make_importer()
        response = MagicMock()
        response.status_code = 200
        response.json.return_value = {"achievements": [{"id": 1}]}

        character = {"realm": {"slug": "silvermoon"}, "name": "Alice"}

        with patch("lifestream.importers.wow.requests.get", return_value=response):
            result = imp.get_character_achievements("usertok", character)

        assert result == [{"id": 1}]

    def test_get_character_achievements_raises_not_found_on_404(self):
        imp = self._make_importer()
        response = MagicMock()
        response.status_code = 404
        character = {"realm": {"slug": "silvermoon"}, "name": "Ghost"}

        with patch("lifestream.importers.wow.requests.get", return_value=response):
            with pytest.raises(WowCharacterNotFound):
                imp.get_character_achievements("usertok", character)

    def test_get_achievement_detail_raises_not_found_on_404(self):
        imp = self._make_importer()
        response = MagicMock()
        response.status_code = 404

        with patch("lifestream.importers.wow.requests.get", return_value=response):
            with pytest.raises(WowAchievementNotFound):
                imp.get_achievement_detail("apptok", 123)

    def test_get_achievement_icon_extracts_icon_asset(self):
        imp = self._make_importer()
        response = MagicMock()
        response.json.return_value = {
            "assets": [
                {"key": "other", "value": "https://example.com/other.jpg"},
                {"key": "icon", "value": "https://example.com/icon.jpg"},
            ]
        }

        with patch("lifestream.importers.wow.requests.get", return_value=response):
            result = imp.get_achievement_icon("apptok", 123)

        assert result == "https://example.com/icon.jpg"

    def test_get_achievement_icon_returns_empty_string_when_missing(self):
        imp = self._make_importer()
        response = MagicMock()
        response.json.return_value = {"assets": []}

        with patch("lifestream.importers.wow.requests.get", return_value=response):
            result = imp.get_achievement_icon("apptok", 123)

        assert result == ""

    def test_log_achievement_adds_entry(self):
        imp = self._make_importer()
        character = {"realm": {"slug": "silvermoon"}, "name": "Alice"}

        with (
            patch.object(
                imp,
                "get_achievement_detail",
                return_value={"name": "Cool Title", "description": "Do the thing"},
            ),
            patch.object(imp, "get_achievement_icon", return_value="icon.jpg"),
        ):
            imp.log_achievement(123, 1577880000000, character, "apptok")

        imp._entry_store.add_entry.assert_called_once()
        args, kwargs = imp._entry_store.add_entry.call_args
        assert args[0] == "gaming"
        assert args[2] == "Cool Title --- Do the thing"
        assert args[3] == "blizzard_wow"
        assert kwargs["image"] == "icon.jpg"
        assert "silvermoon" in kwargs["url"]

    def test_process_character_skips_already_seen_achievements(self):
        imp = self._make_importer()
        character = {"realm": {"slug": "silvermoon"}, "name": "Alice", "level": 60}
        imp._entry_store.get_by_id.return_value = {"systemid": "already-there"}

        with (
            patch.object(
                imp,
                "get_character_achievements",
                return_value=[
                    {"achievement": {"id": 1}, "completed_timestamp": 1577880000000}
                ],
            ),
            patch.object(imp, "log_achievement") as mock_log,
        ):
            imp.process_character(character, "usertok", "apptok")

        mock_log.assert_not_called()

    def test_process_character_skips_achievements_without_completed_timestamp(self):
        imp = self._make_importer()
        character = {"realm": {"slug": "silvermoon"}, "name": "Alice", "level": 60}
        imp._entry_store.get_by_id.return_value = None

        with (
            patch.object(
                imp,
                "get_character_achievements",
                return_value=[{"achievement": {"id": 1}, "completed_timestamp": None}],
            ),
            patch.object(imp, "log_achievement") as mock_log,
        ):
            imp.process_character(character, "usertok", "apptok")

        mock_log.assert_not_called()

    def test_process_character_logs_new_achievements(self):
        imp = self._make_importer()
        character = {"realm": {"slug": "silvermoon"}, "name": "Alice", "level": 60}
        imp._entry_store.get_by_id.return_value = None

        with (
            patch.object(
                imp,
                "get_character_achievements",
                return_value=[
                    {"achievement": {"id": 1}, "completed_timestamp": 1577880000000}
                ],
            ),
            patch.object(imp, "log_achievement") as mock_log,
        ):
            imp.process_character(character, "usertok", "apptok")

        mock_log.assert_called_once_with(1, 1577880000000, character, "apptok")

    def test_process_character_handles_character_not_found(self):
        imp = self._make_importer()
        character = {"realm": {"slug": "silvermoon"}, "name": "Ghost", "level": 60}

        with patch.object(
            imp,
            "get_character_achievements",
            side_effect=WowCharacterNotFound("Ghost on silvermoon"),
        ):
            imp.process_character(character, "usertok", "apptok")  # should not raise

    def test_process_character_skips_single_missing_achievement_but_continues(self):
        imp = self._make_importer()
        character = {"realm": {"slug": "silvermoon"}, "name": "Alice", "level": 60}
        imp._entry_store.get_by_id.return_value = None

        with (
            patch.object(
                imp,
                "get_character_achievements",
                return_value=[
                    {"achievement": {"id": 1}, "completed_timestamp": 1577880000000},
                    {"achievement": {"id": 2}, "completed_timestamp": 1577880000000},
                ],
            ),
            patch.object(
                imp,
                "log_achievement",
                side_effect=[WowAchievementNotFound("1"), None],
            ) as mock_log,
        ):
            imp.process_character(character, "usertok", "apptok")

        assert mock_log.call_count == 2

    def test_process_character_continues_past_unexpected_achievement_error(self):
        """Regression: a schema surprise (e.g. KeyError from an achievement
        missing an expected field) on one achievement must not stop the rest
        of that character's achievements from being processed."""
        imp = self._make_importer()
        character = {"realm": {"slug": "silvermoon"}, "name": "Alice", "level": 60}
        imp._entry_store.get_by_id.return_value = None

        with (
            patch.object(
                imp,
                "get_character_achievements",
                return_value=[
                    {"achievement": {}, "completed_timestamp": 1577880000000},
                    {"achievement": {"id": 2}, "completed_timestamp": 1577880000000},
                ],
            ),
            patch.object(imp, "log_achievement") as mock_log,
        ):
            imp.process_character(character, "usertok", "apptok")  # should not raise

        # The first entry has no "id" key (KeyError), so log_achievement is
        # only reached for the second, well-formed entry.
        mock_log.assert_called_once_with(2, 1577880000000, character, "apptok")

    def test_run_continues_past_unexpected_character_error(self):
        """Regression: an unhandled failure processing one character must
        not stop the rest of the account's characters from being processed."""
        imp = self._make_importer()
        imp.authenticate_user = MagicMock(return_value={"access_token": "usertok"})
        imp.fetch_app_token = MagicMock(return_value="apptok")
        imp.get_account_characters = MagicMock(
            return_value=[{"name": "Alice"}, {"name": "Bob"}]
        )
        imp.process_character = MagicMock(side_effect=[RuntimeError("boom"), None])

        imp.run()  # should not raise

        assert imp.process_character.call_count == 2

    def test_run_authenticates_and_processes_each_character(self):
        imp = self._make_importer()
        imp.authenticate_user = MagicMock(return_value={"access_token": "usertok"})
        imp.fetch_app_token = MagicMock(return_value="apptok")
        imp.get_account_characters = MagicMock(
            return_value=[{"name": "Alice"}, {"name": "Bob"}]
        )
        imp.process_character = MagicMock()

        imp.run()

        assert imp.process_character.call_count == 2
        imp.process_character.assert_any_call({"name": "Alice"}, "usertok", "apptok")
        imp.process_character.assert_any_call({"name": "Bob"}, "usertok", "apptok")
