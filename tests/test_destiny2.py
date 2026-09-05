"""Tests for the Destiny 2 importer."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from lifestream.core import code_fetcher as real_code_fetcher
from lifestream.importers.base import ConfigurationError
from lifestream.importers.destiny2 import (
    Destiny2Importer,
    DestinyAccountNotFound,
    DestinyException,
)


class TestDestiny2Importer:
    def _make_importer(self):
        imp = Destiny2Importer()
        imp._args = imp.parse_args([])
        imp._entry_store = MagicMock()
        imp.get_config = MagicMock(
            side_effect=lambda k, fallback=None: {
                "key": "apikey",
                "client_id": "cid",
                "client_secret": "csecret",
            }.get(k, fallback)
        )
        return imp

    def test_validate_config_fails_when_keys_missing(self):
        imp = Destiny2Importer()
        imp.get_config = MagicMock(return_value=None)
        assert imp.validate_config() is False

    def test_validate_config_passes_when_all_keys_present(self):
        imp = Destiny2Importer()
        imp.get_config = MagicMock(return_value="set")
        assert imp.validate_config() is True

    def test_authenticate_uses_saved_unexpired_token(self):
        imp = self._make_importer()
        future = datetime.now(timezone.utc) + timedelta(days=1)
        token = {
            "access_token": "cached",
            "expire_dt": future,
            "refresh_expire_dt": future,
        }
        imp.load_oauth_token = MagicMock(return_value=token)

        result = imp.authenticate()

        assert result == token

    def test_authenticate_refreshes_expired_access_token(self):
        imp = self._make_importer()
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        future = datetime.now(timezone.utc) + timedelta(days=1)
        token = {
            "access_token": "old",
            "refresh_token": "refreshtok",
            "expire_dt": past,
            "refresh_expire_dt": future,
        }
        imp.load_oauth_token = MagicMock(return_value=token)
        imp.save_oauth_token = MagicMock()

        refresh_response = MagicMock()
        refresh_response.json.return_value = {
            "access_token": "new",
            "expires_in": "3600",
            "refresh_token": "refreshtok",
            "refresh_expires_in": "864000",
        }

        with patch(
            "lifestream.importers.destiny2.requests.post",
            return_value=refresh_response,
        ):
            result = imp.authenticate()

        assert result["access_token"] == "new"
        imp.save_oauth_token.assert_called_once()

    def test_authenticate_raises_when_refresh_token_also_expired(self):
        imp = self._make_importer()
        past = datetime.now(timezone.utc) - timedelta(days=1)
        token = {"expire_dt": past, "refresh_expire_dt": past}
        imp.load_oauth_token = MagicMock(return_value=token)

        with pytest.raises(ConfigurationError, match="reauth"):
            imp.authenticate()

    def test_authenticate_raises_when_refresh_fails(self):
        imp = self._make_importer()
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        future = datetime.now(timezone.utc) + timedelta(days=1)
        token = {
            "access_token": "old",
            "refresh_token": "refreshtok",
            "expire_dt": past,
            "refresh_expire_dt": future,
        }
        imp.load_oauth_token = MagicMock(return_value=token)

        refresh_response = MagicMock()
        refresh_response.json.return_value = {"error": "invalid_grant"}

        with patch(
            "lifestream.importers.destiny2.requests.post",
            return_value=refresh_response,
        ):
            with pytest.raises(ConfigurationError):
                imp.authenticate()

    def test_authenticate_runs_code_fetcher_flow_and_saves_token(self):
        imp = self._make_importer()
        imp.load_oauth_token = MagicMock(return_value=None)
        imp.save_oauth_token = MagicMock()

        token_response = MagicMock()
        token_response.json.return_value = {
            "access_token": "newtoken",
            "expires_in": "3600",
            "refresh_token": "refreshtok",
            "refresh_expires_in": "864000",
        }

        with (
            patch("lifestream.importers.destiny2.code_fetcher") as mock_cf,
            patch(
                "lifestream.importers.destiny2.requests.post",
                return_value=token_response,
            ),
            patch("builtins.print"),
        ):
            mock_cf.are_we_working.return_value = True
            mock_cf.get_code.return_value = {"code": ["abc123"]}

            result = imp.authenticate()

        assert result["access_token"] == "newtoken"
        assert "expire_dt" in result
        imp.save_oauth_token.assert_called_once_with(result)

    def test_authenticate_raises_when_code_fetcher_unavailable(self):
        imp = self._make_importer()
        imp.load_oauth_token = MagicMock(return_value=None)

        with patch("lifestream.importers.destiny2.code_fetcher") as mock_cf:
            mock_cf.WeSayNotToday = real_code_fetcher.WeSayNotToday
            mock_cf.are_we_working.side_effect = real_code_fetcher.WeSayNotToday()

            with pytest.raises(ConfigurationError):
                imp.authenticate()

    def test_destiny_call_returns_response_on_success(self):
        imp = self._make_importer()
        response = MagicMock()
        response.json.return_value = {"ErrorCode": 1, "Response": {"data": "ok"}}
        credentials = {"token_type": "Bearer", "access_token": "tok"}

        with patch(
            "lifestream.importers.destiny2.requests.get", return_value=response
        ) as mock_get:
            result = imp.destiny_call(credentials, "some/path/")

        assert result == {"data": "ok"}
        args, kwargs = mock_get.call_args
        assert args[0] == "https://www.bungie.net/Platform/some/path/"
        assert kwargs["headers"]["X-API-Key"] == "apikey"
        assert kwargs["headers"]["Authorization"] == "Bearer tok"

    def test_destiny_call_raises_destiny_account_not_found(self):
        imp = self._make_importer()
        response = MagicMock()
        response.json.return_value = {
            "ErrorCode": 5,
            "ErrorStatus": "DestinyAccountNotFound",
            "Message": "nope",
        }
        credentials = {"token_type": "Bearer", "access_token": "tok"}

        with patch("lifestream.importers.destiny2.requests.get", return_value=response):
            with pytest.raises(DestinyAccountNotFound):
                imp.destiny_call(credentials, "some/path/")

    def test_destiny_call_raises_generic_destiny_exception_for_unknown_error(self):
        imp = self._make_importer()
        response = MagicMock()
        response.json.return_value = {
            "ErrorCode": 99,
            "ErrorStatus": "SomeOtherError",
            "Message": "weird",
        }
        credentials = {"token_type": "Bearer", "access_token": "tok"}

        with patch("lifestream.importers.destiny2.requests.get", return_value=response):
            with pytest.raises(DestinyException):
                imp.destiny_call(credentials, "some/path/")

    def test_log_activity_adds_entry_with_icon(self):
        imp = self._make_importer()
        instance = {
            "activityDetails": {"referenceId": 42},
            "period": "2020-01-01T12:00:00Z",
        }
        activity = {
            "displayProperties": {
                "name": "Cool Strike",
                "description": "Do the thing",
                "hasIcon": True,
                "icon": "/icon.jpg",
            }
        }
        character_data = {"emblemPath": "/emblem.jpg"}

        imp.log_activity(instance, activity, "char1", character_data)

        imp._entry_store.add_entry.assert_called_once()
        args, kwargs = imp._entry_store.add_entry.call_args
        assert args[0] == "gaming"
        assert args[2] == "Cool Strike --- Do the thing"
        assert args[3] == "destiny2"
        assert kwargs["image"] == "https://www.bungie.net/icon.jpg"
        assert kwargs["url"] == ""

    def test_log_activity_falls_back_to_emblem_when_no_icon(self):
        imp = self._make_importer()
        instance = {
            "activityDetails": {"referenceId": 42},
            "period": "2020-01-01T12:00:00Z",
        }
        activity = {
            "displayProperties": {
                "name": "Cool Strike",
                "description": "Do the thing",
                "hasIcon": False,
            }
        }
        character_data = {"emblemPath": "/emblem.jpg"}

        imp.log_activity(instance, activity, "char1", character_data)

        _, kwargs = imp._entry_store.add_entry.call_args
        assert kwargs["image"] == "https://www.bungie.net/emblem.jpg"

    def test_log_activity_skips_when_no_name(self):
        imp = self._make_importer()
        instance = {
            "activityDetails": {"referenceId": 42},
            "period": "2020-01-01T12:00:00Z",
        }
        activity = {"displayProperties": {}}

        imp.log_activity(instance, activity, "char1", {})

        imp._entry_store.add_entry.assert_not_called()

    def test_process_character_skips_incomplete_activities(self):
        imp = self._make_importer()
        activities_response = {
            "activities": [
                {
                    "activityDetails": {"referenceId": 1},
                    "values": {"completed": {"basic": {"value": 0}}},
                }
            ]
        }

        with (
            patch.object(imp, "destiny_call", return_value=activities_response),
            patch.object(imp, "destiny_entity") as mock_entity,
        ):
            imp.process_character(
                {"membershipType": 1, "membershipId": "m1"},
                {"membershipType": 1, "membershipId": "m1"},
                "char1",
                {},
            )

        mock_entity.assert_not_called()

    def test_process_character_logs_completed_activities(self):
        imp = self._make_importer()
        activities_response = {
            "activities": [
                {
                    "activityDetails": {"referenceId": 1},
                    "values": {"completed": {"basic": {"value": 1}}},
                    "period": "2020-01-01T12:00:00Z",
                }
            ]
        }
        activity_def = {"displayProperties": {"name": "A", "description": "B"}}

        with (
            patch.object(imp, "destiny_call", return_value=activities_response),
            patch.object(imp, "destiny_entity", return_value=activity_def),
            patch.object(imp, "log_activity") as mock_log,
        ):
            imp.process_character(
                {"membershipType": 1, "membershipId": "m1"},
                {"membershipType": 1, "membershipId": "m1"},
                "char1",
                {},
            )

        mock_log.assert_called_once()

    def test_process_character_continues_past_activity_error(self):
        """Regression: one malformed activity instance shouldn't stop the
        rest of the character's activities from being processed."""
        imp = self._make_importer()
        activities_response = {
            "activities": [
                {"activityDetails": {}},  # missing referenceId -> KeyError
                {
                    "activityDetails": {"referenceId": 1},
                    "values": {"completed": {"basic": {"value": 1}}},
                    "period": "2020-01-01T12:00:00Z",
                },
            ]
        }
        activity_def = {"displayProperties": {"name": "A", "description": "B"}}

        with (
            patch.object(imp, "destiny_call", return_value=activities_response),
            patch.object(imp, "destiny_entity", return_value=activity_def),
            patch.object(imp, "log_activity") as mock_log,
        ):
            imp.process_character(
                {"membershipType": 1, "membershipId": "m1"},
                {"membershipType": 1, "membershipId": "m1"},
                "char1",
                {},
            )

        mock_log.assert_called_once()

    def test_run_skips_members_without_destiny_account(self):
        imp = self._make_importer()
        imp.authenticate = MagicMock(
            return_value={"token_type": "Bearer", "access_token": "t"}
        )

        with patch.object(
            imp,
            "destiny_call",
            side_effect=[
                {"destinyMemberships": [{"membershipType": 1, "membershipId": "m1"}]},
                DestinyAccountNotFound("no account"),
            ],
        ):
            imp.run()  # should not raise

    def test_run_processes_each_character_and_continues_past_errors(self):
        imp = self._make_importer()
        imp.authenticate = MagicMock(
            return_value={"token_type": "Bearer", "access_token": "t"}
        )

        memberships_response = {
            "destinyMemberships": [{"membershipType": 1, "membershipId": "m1"}]
        }
        profile_response = {
            "characters": {"data": {"c1": {"level": 1}, "c2": {"level": 2}}}
        }

        with (
            patch.object(
                imp,
                "destiny_call",
                side_effect=[memberships_response, profile_response],
            ),
            patch.object(
                imp,
                "process_character",
                side_effect=[RuntimeError("boom"), None],
            ) as mock_process,
        ):
            imp.run()  # should not raise despite the first character erroring

        assert mock_process.call_count == 2

    def test_run_backs_off_when_recently_throttled(self):
        imp = self._make_importer()
        imp.authenticate = MagicMock()

        with patch("lifestream.importers.destiny2.should_backoff", return_value=True):
            imp.run()

        imp.authenticate.assert_not_called()
