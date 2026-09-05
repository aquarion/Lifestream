"""Tests for the Foursquare importer."""

from unittest.mock import MagicMock, patch

import pytest

from lifestream.core import code_fetcher as real_code_fetcher
from lifestream.importers.base import ConfigurationError
from lifestream.importers.foursquare import FoursquareImporter


class TestFoursquareImporter:
    def _make_importer(self):
        imp = FoursquareImporter()
        imp._args = imp.parse_args([])
        imp._entry_store = MagicMock()
        return imp

    def test_validate_config_fails_when_keys_missing(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value=None)
        assert imp.validate_config() is False

    def test_validate_config_passes_when_all_keys_present(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value="set")
        assert imp.validate_config() is True

    def test_authenticate_uses_saved_token_without_reauth(self):
        imp = self._make_importer()
        imp.load_oauth_token = MagicMock(return_value="cached-token")

        result = imp.authenticate()

        assert result == "cached-token"

    def test_authenticate_runs_code_fetcher_flow_and_saves_token(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(
            side_effect=lambda k, fallback=None: {
                "client_id": "cid",
                "secret": "csecret",
            }.get(k, fallback)
        )
        imp.load_oauth_token = MagicMock(return_value=None)
        imp.save_oauth_token = MagicMock()

        token_response = MagicMock()
        token_response.json.return_value = {"access_token": "newtoken"}

        with (
            patch("lifestream.importers.foursquare.code_fetcher") as mock_cf,
            patch(
                "lifestream.importers.foursquare.secrets.token_urlsafe",
                return_value="expected-state",
            ),
            patch(
                "lifestream.importers.foursquare.requests.get",
                return_value=token_response,
            ) as mock_get,
            patch("builtins.print"),
        ):
            mock_cf.are_we_working.return_value = True
            mock_cf.get_url.return_value = "https://example.com/keyback/"
            mock_cf.get_code.return_value = {
                "code": ["abc123"],
                "state": ["expected-state"],
            }

            result = imp.authenticate()

        assert result == "newtoken"
        imp.save_oauth_token.assert_called_once_with("newtoken")
        mock_get.assert_called_once_with(
            "https://foursquare.com/oauth2/access_token",
            params={
                "client_id": "cid",
                "client_secret": "csecret",
                "grant_type": "authorization_code",
                "redirect_uri": "https://example.com/keyback/",
                "code": "abc123",
            },
            timeout=30,
        )

    def test_authenticate_raises_on_oauth_state_mismatch(self):
        """Regression: a callback with a mismatched (or missing) state must
        be rejected, since state is what protects this flow from CSRF/token
        injection."""
        imp = self._make_importer()
        imp.get_config = MagicMock(
            side_effect=lambda k, fallback=None: {
                "client_id": "cid",
                "secret": "csecret",
            }.get(k, fallback)
        )
        imp.load_oauth_token = MagicMock(return_value=None)
        imp.save_oauth_token = MagicMock()

        with (
            patch("lifestream.importers.foursquare.code_fetcher") as mock_cf,
            patch(
                "lifestream.importers.foursquare.secrets.token_urlsafe",
                return_value="expected-state",
            ),
            patch("builtins.print"),
        ):
            mock_cf.are_we_working.return_value = True
            mock_cf.get_url.return_value = "https://example.com/keyback/"
            mock_cf.get_code.return_value = {
                "code": ["abc123"],
                "state": ["attacker-supplied-state"],
            }

            with pytest.raises(ConfigurationError, match="state mismatch"):
                imp.authenticate()

        imp.save_oauth_token.assert_not_called()

    def test_authenticate_falls_back_to_manual_code_paste_when_code_fetcher_unavailable(
        self,
    ):
        imp = self._make_importer()
        imp.get_config = MagicMock(
            side_effect=lambda k, fallback=None: {
                "client_id": "cid",
                "secret": "csecret",
            }.get(k, fallback)
        )
        imp.load_oauth_token = MagicMock(return_value=None)
        imp.save_oauth_token = MagicMock()

        token_response = MagicMock()
        token_response.json.return_value = {"access_token": "pastedtoken"}

        with (
            patch("lifestream.importers.foursquare.code_fetcher") as mock_cf,
            patch(
                "lifestream.importers.foursquare.requests.get",
                return_value=token_response,
            ),
            patch("builtins.input", return_value="pastedcode"),
            patch("builtins.print"),
        ):
            mock_cf.WeSayNotToday = real_code_fetcher.WeSayNotToday
            mock_cf.are_we_working.side_effect = real_code_fetcher.WeSayNotToday()

            result = imp.authenticate()

        assert result == "pastedtoken"

    def test_checkin_source_reports_mayor(self):
        assert FoursquareImporter._checkin_source({"isMayor": True}) == (
            "Foursquare-Mayor"
        )
        assert FoursquareImporter._checkin_source({"isMayor": False}) == "Foursquare"
        assert FoursquareImporter._checkin_source({}) == "Foursquare"

    def test_checkin_message_and_image_uses_venue_primary_category_icon(self):
        checkin = {
            "venue": {
                "name": "The Pub",
                "categories": [
                    {"primary": False, "icon": {"prefix": "wrong/"}},
                    {"primary": True, "icon": {"prefix": "right/"}},
                ],
            }
        }
        message, image = FoursquareImporter._checkin_message_and_image(checkin)
        assert message == "The Pub"
        assert image == "right/64.png"

    def test_checkin_message_and_image_falls_back_to_location_name_without_venue(self):
        checkin = {"location": {"name": "Somewhere"}}
        message, image = FoursquareImporter._checkin_message_and_image(checkin)
        assert message == "Somewhere"
        assert image == ""

    def test_process_checkin_adds_entry_and_location_for_venue_checkin(self):
        imp = self._make_importer()
        checkin = {
            "id": "chk1",
            "createdAt": 1577880000,
            "isMayor": False,
            "venue": {
                "name": "The Pub",
                "categories": [],
                "location": {"lat": 51.5, "lng": -0.1},
            },
        }

        imp.process_checkin(checkin, "someuser")

        imp._entry_store.add_entry.assert_called_once()
        args, kwargs = imp._entry_store.add_entry.call_args
        assert args[0] == "location"
        assert args[1] == "chk1"
        assert args[2] == "The Pub"
        assert args[3] == "Foursquare"
        assert kwargs["url"] == "https://www.foursquare.com/someuser/checkin/chk1"

        imp._entry_store.add_location.assert_called_once()
        loc_args = imp._entry_store.add_location.call_args.args
        assert loc_args[1] == "foursquare"
        assert loc_args[2] == 51.5
        assert loc_args[3] == -0.1

    def test_process_checkin_skips_location_when_no_venue(self):
        imp = self._make_importer()
        checkin = {
            "id": "chk2",
            "createdAt": 1577880000,
            "location": {"name": "Somewhere"},
        }

        imp.process_checkin(checkin, "someuser")

        imp._entry_store.add_entry.assert_called_once()
        imp._entry_store.add_location.assert_not_called()

    def test_run_authenticates_and_processes_each_checkin(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value="someuser")
        imp.authenticate = MagicMock(return_value="tok")
        imp.process_checkin = MagicMock()

        checkins_response = MagicMock()
        checkins_response.json.return_value = {
            "response": {"checkins": {"items": [{"id": "a"}, {"id": "b"}]}}
        }

        with patch(
            "lifestream.importers.foursquare.requests.get",
            return_value=checkins_response,
        ) as mock_get:
            imp.run()

        mock_get.assert_called_once_with(
            "https://api.foursquare.com/v2/users/self/checkins",
            params={"v": "20180226", "oauth_token": "tok"},
            timeout=30,
        )
        assert imp.process_checkin.call_count == 2
        imp.process_checkin.assert_any_call({"id": "a"}, "someuser")
        imp.process_checkin.assert_any_call({"id": "b"}, "someuser")
