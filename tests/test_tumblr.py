"""Tests for Tumblr importer."""

from unittest.mock import MagicMock, patch

import pytest

from lifestream.importers.base import ConfigurationError
from lifestream.importers.tumblr import TumblrImporter, authenticate


class TestAuthenticate:
    def test_uses_saved_token_without_reauth(self):
        imp = MagicMock()
        imp.args.reauth = False
        imp.get_config.side_effect = lambda k: {
            "consumer_key": "ckey",
            "secret_key": "csecret",
        }[k]
        imp.load_oauth_token.return_value = {
            "oauth_token": "tok",
            "oauth_token_secret": "toksecret",
        }

        with patch("lifestream.importers.tumblr.TumblrRestClient") as mock_client:
            authenticate(imp)

        mock_client.assert_called_once_with("ckey", "csecret", "tok", "toksecret")
        imp.save_oauth_token.assert_not_called()

    def test_reauth_flag_skips_saved_token_and_runs_oauth_flow(self):
        imp = MagicMock()
        imp.args.reauth = True
        imp.get_config.side_effect = lambda k: {
            "consumer_key": "ckey",
            "secret_key": "csecret",
        }[k]

        mock_sessions = [MagicMock(), MagicMock()]
        mock_sessions[0].fetch_request_token.return_value = {
            "oauth_token": "reqtok",
            "oauth_token_secret": "reqsecret",
        }
        mock_sessions[1].fetch_access_token.return_value = {
            "oauth_token": "newtok",
            "oauth_token_secret": "newsecret",
        }

        with (
            patch(
                "lifestream.importers.tumblr.OAuth1Session",
                side_effect=mock_sessions,
            ),
            patch("lifestream.importers.tumblr.TumblrRestClient") as mock_client,
            patch("builtins.input", side_effect=["y", "1234"]),
            patch("builtins.print"),
        ):
            authenticate(imp)

        imp.load_oauth_token.assert_not_called()
        imp.save_oauth_token.assert_called_once_with(
            {"oauth_token": "newtok", "oauth_token_secret": "newsecret"}
        )
        mock_client.assert_called_once_with("ckey", "csecret", "newtok", "newsecret")

    def test_raises_configuration_error_when_request_token_fetch_fails(self):
        from requests_oauthlib.oauth1_session import TokenRequestDenied

        imp = MagicMock()
        imp.args.reauth = True
        imp.get_config.side_effect = lambda k: {
            "consumer_key": "ckey",
            "secret_key": "csecret",
        }[k]

        mock_session = MagicMock()
        mock_session.fetch_request_token.side_effect = TokenRequestDenied(
            "Token request failed with code 401, response was 'nope'.",
            MagicMock(),
        )

        with patch(
            "lifestream.importers.tumblr.OAuth1Session", return_value=mock_session
        ):
            with pytest.raises(ConfigurationError):
                authenticate(imp)

        imp.save_oauth_token.assert_not_called()


class TestTumblrImporter:
    def _make_importer(self):
        imp = TumblrImporter()
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

    def test_get_oauth_path_uses_configured_secrets_file(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value="/path/to/secrets.oauth")
        assert imp.get_oauth_path() == "/path/to/secrets.oauth"

    def test_post_title_prefers_title_then_falls_back(self):
        assert TumblrImporter._post_title({"type": "text", "title": "Hi"}) == "Hi"
        assert (
            TumblrImporter._post_title({"type": "text", "caption": "Caption"})
            == "Caption"
        )
        assert TumblrImporter._post_title({"type": "link"}) == "Tumblr link"

    def test_post_title_quote_uses_text_even_with_title(self):
        post = {"type": "quote", "title": "ignored", "text": "The actual quote"}
        assert TumblrImporter._post_title(post) == "The actual quote"

    def test_process_blog_stops_on_api_error(self):
        imp = self._make_importer()
        tumblr = MagicMock()
        tumblr.posts.return_value = {"errors": True, "meta": {"msg": "nope"}}

        result = imp.process_blog(tumblr, "someblog", full_import=False)

        assert result is False
        imp._entry_store.add_entry.assert_not_called()

    def test_process_blog_adds_entries_for_each_post(self):
        imp = self._make_importer()
        tumblr = MagicMock()
        tumblr.posts.return_value = {
            "blog": {"posts": 1},
            "posts": [
                {
                    "type": "text",
                    "id": "123",
                    "title": "A post",
                    "date": "2020-01-01 12:00:00 GMT",
                    "post_url": "http://example.tumblr.com/post/123",
                }
            ],
        }

        result = imp.process_blog(tumblr, "someblog", full_import=False)

        assert result is True
        imp._entry_store.add_entry.assert_called_once()
        args = imp._entry_store.add_entry.call_args.args
        assert args[0] == "text"
        assert args[1] == "123"
        assert args[3] == "tumblr"

    def test_process_blog_stops_on_error_mid_pagination(self):
        """A paginated fetch returning an error response fails the blog instead of KeyError-ing."""
        imp = self._make_importer()
        tumblr = MagicMock()
        tumblr.posts.side_effect = [
            {"blog": {"posts": 100}},
            {"errors": True, "meta": {"msg": "rate limited"}},
        ]

        result = imp.process_blog(tumblr, "someblog", full_import=True)

        assert result is False
        imp._entry_store.add_entry.assert_not_called()

    def test_run_authenticates_and_processes_each_configured_blog(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value="blog1,blog2")
        imp.process_blog = MagicMock(return_value=True)

        with patch(
            "lifestream.importers.tumblr.authenticate", return_value="tumblr-client"
        ) as mock_auth:
            imp.run()

        mock_auth.assert_called_once_with(imp)
        assert imp.process_blog.call_count == 2
        imp.process_blog.assert_any_call("tumblr-client", "blog1", False)
        imp.process_blog.assert_any_call("tumblr-client", "blog2", False)

    def test_run_raises_when_a_blog_fails_but_still_processes_the_rest(self):
        """One failing blog is reported, but doesn't stop the others from being tried."""
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value="blog1,blog2,blog3")
        imp.process_blog = MagicMock(side_effect=[True, False, True])

        with patch(
            "lifestream.importers.tumblr.authenticate", return_value="tumblr-client"
        ):
            with pytest.raises(RuntimeError, match="blog2"):
                imp.run()

        assert imp.process_blog.call_count == 3
