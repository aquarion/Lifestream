"""Tests for shared Facebook Graph API auth/filtering/persistence logic."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pymysql
import pytest

from lifestream.importers.base import ConfigurationError
from lifestream.importers.facebook_posts import FacebookPostsImporter


class TestFacebookBaseImporter:
    def _make_importer(self):
        imp = FacebookPostsImporter()
        imp._args = imp.parse_args([])
        imp._entry_store = MagicMock()
        return imp

    def test_validate_config_requires_appid_and_secret(self):
        imp = FacebookPostsImporter()
        imp.get_config = MagicMock(return_value=None)
        assert imp.validate_config() is False

    def test_authenticate_uses_saved_token_without_reauth(self):
        imp = self._make_importer()
        imp.load_oauth_token = MagicMock(return_value={"access_token": "cached"})

        result = imp.authenticate()

        assert result == {"access_token": "cached"}

    def test_authenticate_runs_code_fetcher_flow_and_saves_token(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(
            side_effect=lambda k, fallback=None: {
                "appid": "app1",
                "secret": "sec1",
            }.get(k, fallback)
        )
        imp.load_oauth_token = MagicMock(return_value=None)
        imp.save_oauth_token = MagicMock()

        extend_response = MagicMock()
        extend_response.json.return_value = {
            "access_token": "newtoken",
            "expires_in": "3600",
        }

        with (
            patch("lifestream.importers.facebook_base.code_fetcher") as mock_cf,
            patch(
                "lifestream.importers.facebook_base.requests.get",
                return_value=extend_response,
            ),
            patch("builtins.print"),
        ):
            mock_cf.are_we_working.return_value = True
            mock_cf.get_url.return_value = "https://example.com/keyback/"
            mock_cf.get_code.return_value = {"access_token": ["abc123"]}

            result = imp.authenticate()

        assert result["access_token"] == "newtoken"
        assert "expire_dt" in result
        imp.save_oauth_token.assert_called_once_with(result)

    def test_authenticate_falls_back_to_pin_entry_when_code_fetcher_unavailable(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(
            side_effect=lambda k, fallback=None: {
                "appid": "app1",
                "secret": "sec1",
                "base": "https://dayze.example.com",
            }.get(k, fallback)
        )
        imp.load_oauth_token = MagicMock(return_value=None)
        imp.save_oauth_token = MagicMock()

        extend_response = MagicMock()
        extend_response.json.return_value = {
            "access_token": "pintoken",
            "expires_in": "3600",
        }

        with (
            patch("lifestream.importers.facebook_base.code_fetcher") as mock_cf,
            patch("lifestream.importers.facebook_base.raw_config") as mock_raw_config,
            patch(
                "lifestream.importers.facebook_base.requests.get",
                return_value=extend_response,
            ),
            patch("builtins.input", return_value="1234"),
            patch("builtins.print"),
        ):
            from lifestream.core import code_fetcher as real_code_fetcher

            mock_cf.WeSayNotToday = real_code_fetcher.WeSayNotToday
            mock_cf.are_we_working.side_effect = real_code_fetcher.WeSayNotToday()
            mock_raw_config.get.return_value = "https://dayze.example.com"

            result = imp.authenticate()

        assert result["access_token"] == "pintoken"

    def test_check_token_expiry_raises_configuration_error_when_expired(self):
        imp = self._make_importer()
        credentials = {"expire_dt": datetime.now() - timedelta(days=1)}
        with pytest.raises(ConfigurationError, match="expired"):
            imp.check_token_expiry(credentials)

    def test_check_token_expiry_warns_but_does_not_raise_when_expiring_soon(self):
        imp = self._make_importer()
        credentials = {"expire_dt": datetime.now() + timedelta(days=3)}
        with patch(
            "lifestream.importers.facebook_base.check_and_set_backoff",
            return_value=False,
        ):
            imp.check_token_expiry(credentials)  # should not raise

    def test_post_is_visible_keeps_non_custom_privacy(self):
        post = {"privacy": {"value": "EVERYONE"}}
        assert FacebookPostsImporter._post_is_visible(post, "url", {}, set()) is True

    def test_post_is_visible_hides_custom_with_no_allow_list(self):
        post = {"privacy": {"value": "CUSTOM", "allow": ""}}
        assert FacebookPostsImporter._post_is_visible(post, "url", {}, set()) is False

    def test_post_is_visible_respects_filter_membership(self):
        post = {"privacy": {"value": "CUSTOM", "allow": "111"}}
        filters = {"111": "LARP"}
        assert (
            FacebookPostsImporter._post_is_visible(post, "url", filters, {"LARP"})
            is True
        )
        assert (
            FacebookPostsImporter._post_is_visible(post, "url", filters, {"Other"})
            is False
        )

    def test_post_is_visible_does_not_substring_match_filter_names(self):
        """Regression: visible_filters must be an exact-name set, not a substring check."""
        post = {"privacy": {"value": "CUSTOM", "allow": "111"}}
        filters = {"111": "War"}
        assert (
            FacebookPostsImporter._post_is_visible(post, "url", filters, {"Warcraft"})
            is False
        )

    def test_process_post_skips_self_privacy(self):
        imp = self._make_importer()
        post = {"privacy": {"value": "SELF"}, "id": "1_1"}
        imp.process_post(post, {"id": "1"})
        imp._entry_store.add_entry.assert_not_called()

    def test_process_post_skips_twitter_crossposts(self):
        imp = self._make_importer()
        post = {
            "application": {"namespace": "twitter"},
            "privacy": {"value": "EVERYONE"},
            "id": "1_1",
        }
        imp.process_post(post, {"id": "1"})
        imp._entry_store.add_entry.assert_not_called()

    def test_process_post_adds_visible_post(self):
        imp = self._make_importer()
        post = {
            "id": "1_2",
            "type": "status",
            "message": "hello",
            "privacy": {"value": "EVERYONE"},
            "created_time": "2024-01-01T12:00:00+0000",
        }
        imp.process_post(post, {"id": "1"})

        imp._entry_store.add_entry.assert_called_once()
        args = imp._entry_store.add_entry.call_args.args
        assert args[0] == "status"
        assert args[1] == "1_2"
        assert args[3] == "facebook"

    def test_process_post_swallows_mysql_truncation_error(self):
        """A 1366 (bad string value, e.g. malformed emoji) error is logged, not raised."""
        imp = self._make_importer()
        imp._entry_store.add_entry.side_effect = pymysql.err.InternalError(
            1366, "Incorrect string value"
        )
        post = {
            "id": "1_3",
            "type": "status",
            "message": "hello",
            "privacy": {"value": "EVERYONE"},
            "created_time": "2024-01-01T12:00:00+0000",
        }
        imp.process_post(post, {"id": "1"})  # should not raise
