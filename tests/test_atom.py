"""Tests for Atom/RSS feed importer."""

from unittest.mock import MagicMock, patch

import pytest

from lifestream.importers.atom import AtomImporter


class TestAtomImporter:
    def _make_importer(self):
        imp = AtomImporter()
        imp._args = imp.parse_args(["test_type", "http://example.com/feed"])
        imp._entry_store = MagicMock()
        return imp

    def test_run_raises_on_bozo_feed(self):
        """A network failure (URLError) raises RuntimeError."""
        import urllib.error

        imp = self._make_importer()

        mock_fp_obj = MagicMock()
        mock_fp_obj.status = 200
        mock_fp_obj.bozo = True
        mock_fp_obj.bozo_exception = urllib.error.URLError("connection refused")
        mock_fp_obj.__getitem__ = lambda _, k: []

        with patch("feedparser.parse", return_value=mock_fp_obj):
            with pytest.raises(RuntimeError, match="Failed to fetch feed"):
                imp.run()

    def test_run_warns_on_malformed_but_parseable_feed(self):
        """A bozo feed with recoverable entries logs a warning but still imports them."""
        imp = self._make_importer()

        entry = {
            "guid": "1",
            "updated_parsed": (2024, 1, 1, 12, 0, 0, 0, 1, 0),
            "title": "Recovered entry",
            "links": [{"href": "http://x.com/1"}],
        }
        mock_fp_obj = MagicMock()
        mock_fp_obj.status = 200
        mock_fp_obj.bozo = True
        mock_fp_obj.bozo_exception = Exception("not well-formed")
        mock_fp_obj.__getitem__ = lambda _, k: [entry] if k == "entries" else []

        with patch("feedparser.parse", return_value=mock_fp_obj):
            imp.run()

        imp._entry_store.add_entry.assert_called_once()

    def test_run_raises_on_http_error_status(self):
        """A feed fetch returning an HTTP error status raises RuntimeError."""
        imp = self._make_importer()

        mock_fp_obj = MagicMock()
        mock_fp_obj.status = 403
        mock_fp_obj.bozo = False
        mock_fp_obj.__getitem__ = lambda _, k: []

        with patch("feedparser.parse", return_value=mock_fp_obj):
            with pytest.raises(RuntimeError, match="HTTP 403"):
                imp.run()

        imp._entry_store.add_entry.assert_not_called()

    def test_run_skips_entries_with_no_date(self):
        """Entries with updated_parsed=None are skipped without crashing."""
        imp = self._make_importer()

        entry = {
            "guid": "1",
            "updated_parsed": None,
            "title": "No-date entry",
            "links": [{"href": "http://x.com"}],
        }
        mock_fp_obj = MagicMock()
        mock_fp_obj.status = 200
        mock_fp_obj.bozo = False
        mock_fp_obj.__getitem__ = lambda _, k: [entry] if k == "entries" else []

        with patch("feedparser.parse", return_value=mock_fp_obj):
            imp.run()

        imp._entry_store.add_entry.assert_not_called()
