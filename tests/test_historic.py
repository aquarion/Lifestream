"""Tests for the historic Tumblr reblog importer."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch

from lifestream.importers.historic import HistoricImporter


class TestHistoricImporter:
    def _make_importer(self):
        imp = HistoricImporter()
        imp._args = imp.parse_args([])
        imp._entry_store = MagicMock()
        imp._entry_store.no_db = False
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

    def test_run_skips_reblog_and_auth_when_nothing_in_window(self):
        """No matching rows means no OAuth flow is even triggered."""
        imp = self._make_importer()
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = []
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        imp._entry_store.dbcxn.cursor.return_value = mock_cursor

        with patch("lifestream.importers.historic.authenticate") as mock_auth:
            imp.run()

        mock_auth.assert_not_called()

    def test_run_reblogs_matching_post(self):
        imp = self._make_importer()
        fulldata = json.dumps({"reblog_key": "rbkey123"})
        row = (
            "A title",
            datetime(2016, 8, 3, 10, 0, 0),
            "http://example.tumblr.com/post/1",
            fulldata,
            "systemid1",
            "tumblr",
            "text",
        )
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = [row]
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        imp._entry_store.dbcxn.cursor.return_value = mock_cursor

        mock_tumblr = MagicMock()
        with patch(
            "lifestream.importers.historic.authenticate", return_value=mock_tumblr
        ):
            imp.run()

        mock_tumblr.reblog.assert_called_once()
        _, kwargs = mock_tumblr.reblog.call_args
        assert kwargs["id"] == "systemid1"
        assert kwargs["reblog_key"] == "rbkey123"
        assert kwargs["state"] == "queue"

    def test_run_does_not_touch_dbcxn_in_no_db_mode(self):
        """--no-db must not crash by reaching for a cursor on a None dbcxn."""
        imp = self._make_importer()
        imp._entry_store.no_db = True
        imp._entry_store.dbcxn = None

        with patch("lifestream.importers.historic.authenticate") as mock_auth:
            imp.run()  # should not raise

        mock_auth.assert_not_called()

    def test_run_skips_rows_without_title_or_fulldata(self):
        imp = self._make_importer()
        when = datetime(2016, 8, 3, 10, 0, 0)
        rows = [
            (None, when, "url", "{}", "id1", "tumblr", "text"),
            ("Has title", when, "url", None, "id2", "tumblr", "text"),
        ]
        mock_cursor = MagicMock()
        mock_cursor.fetchall.return_value = rows
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        imp._entry_store.dbcxn.cursor.return_value = mock_cursor

        mock_tumblr = MagicMock()
        with patch(
            "lifestream.importers.historic.authenticate", return_value=mock_tumblr
        ):
            imp.run()

        mock_tumblr.reblog.assert_not_called()
