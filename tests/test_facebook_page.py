"""Tests for the Facebook Page posts importer."""

from unittest.mock import MagicMock, patch

from lifestream.importers.facebook_page import FacebookPageImporter


class TestFacebookPageImporter:
    def _make_importer(self, args=None):
        imp = FacebookPageImporter()
        imp._args = imp.parse_args(args or [])
        imp._entry_store = MagicMock()
        imp.authenticate = MagicMock(return_value={"access_token": "tok"})
        imp.check_token_expiry = MagicMock()
        imp.process_post = MagicMock()
        imp.get_config = MagicMock(
            side_effect=lambda k, fallback=None: {"page_id": "somepage"}.get(
                k, fallback
            )
        )
        return imp

    def test_validate_config_requires_page_id(self):
        imp = FacebookPageImporter()
        imp.get_config = MagicMock(
            side_effect=lambda k, fallback=None: {
                "appid": "app",
                "secret": "sec",
            }.get(k, fallback)
        )
        assert imp.validate_config() is False

    def test_validate_config_passes_with_page_id_and_credentials(self):
        imp = FacebookPageImporter()
        imp.get_config = MagicMock(return_value="set")
        assert imp.validate_config() is True

    def test_run_fetches_configured_page_not_me(self):
        imp = self._make_importer()
        imp.graph_get = MagicMock(
            side_effect=[{"id": "somepage"}, {"data": [], "paging": {}}]
        )

        with patch("lifestream.importers.facebook_base.requests.get"):
            imp.run()

        first_call_args = imp.graph_get.call_args_list[0].args
        second_call_args = imp.graph_get.call_args_list[1].args
        assert first_call_args[1] == "somepage"
        assert second_call_args[1] == "somepage/posts"

    def test_run_stops_after_configured_page_limit(self):
        imp = self._make_importer(["--pages", "1"])
        imp.graph_get = MagicMock(
            side_effect=[
                {"id": "somepage"},
                {"data": [{"id": "1"}], "paging": {"next": "https://next"}},
            ]
        )

        with patch("lifestream.importers.facebook_base.requests.get") as mock_get:
            imp.run()

        mock_get.assert_not_called()
        imp.process_post.assert_called_once()
