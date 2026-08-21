"""Tests for the Facebook timeline posts importer."""

from unittest.mock import MagicMock, patch

from lifestream.importers.facebook_posts import FacebookPostsImporter


class TestFacebookPostsImporter:
    def _make_importer(self, args=None):
        imp = FacebookPostsImporter()
        imp._args = imp.parse_args(args or [])
        imp._entry_store = MagicMock()
        imp.authenticate = MagicMock(return_value={"access_token": "tok"})
        imp.check_token_expiry = MagicMock()
        imp.process_post = MagicMock()
        return imp

    def test_run_stops_after_configured_page_limit(self):
        imp = self._make_importer(["--pages", "2"])
        page_response = {"data": [{"id": "1"}], "paging": {"next": "https://next"}}
        imp.graph_get = MagicMock(side_effect=[{"id": "me"}, page_response])

        next_response = MagicMock()
        next_response.json.return_value = page_response
        with patch(
            "lifestream.importers.facebook_base.requests.get",
            return_value=next_response,
        ) as mock_get:
            imp.run()

        assert (
            mock_get.call_count == 1
        )  # one page fetched via "next", then stop at limit
        assert imp.process_post.call_count == 2  # one post per page, 2 pages

    def test_run_stops_when_no_next_page(self):
        imp = self._make_importer(["--pages", "5"])
        imp.graph_get = MagicMock(
            side_effect=[{"id": "me"}, {"data": [{"id": "1"}], "paging": {}}]
        )

        with patch("lifestream.importers.facebook_base.requests.get") as mock_get:
            imp.run()

        mock_get.assert_not_called()
        imp.process_post.assert_called_once()

    def test_run_ignores_page_limit_with_all_flag(self):
        imp = self._make_importer(["--all"])
        first_page = {"data": [{"id": "1"}], "paging": {"next": "https://next"}}
        imp.graph_get = MagicMock(side_effect=[{"id": "me"}, first_page])

        second_response = MagicMock()
        second_response.json.return_value = {"data": [{"id": "2"}], "paging": {}}
        with patch(
            "lifestream.importers.facebook_base.requests.get",
            return_value=second_response,
        ):
            imp.run()

        assert imp.process_post.call_count == 2
