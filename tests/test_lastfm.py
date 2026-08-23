"""Tests for Last.fm scrobble importer."""

from unittest.mock import MagicMock, patch

import pytest

from lifestream.importers.lastfm import LastfmImporter


class _FeedEntry(dict):
    """Minimal stand-in for feedparser's FeedParserDict (dict + attribute access)."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


def _make_fp(entries, status=200, bozo=False, bozo_exception=None):
    """Build a MagicMock standing in for feedparser's top-level FeedParserDict."""
    fp = MagicMock()
    fp.status = status
    fp.bozo = bozo
    fp.bozo_exception = bozo_exception
    fp.__getitem__ = lambda _, k: entries if k == "entries" else []
    return fp


class TestLastfmImporter:
    def _make_importer(self):
        imp = LastfmImporter()
        imp._entry_store = MagicMock()
        imp.get_config = MagicMock(return_value="testuser")
        return imp

    def test_run_processes_all_entries_including_first(self):
        """Regression test for the off-by-one bug that used to skip fp['entries'][0]."""
        imp = self._make_importer()

        entries = [
            _FeedEntry(
                guid="1",
                title="First Song",
                updated="2024-01-01T12:00:00Z",
                link="http://last.fm/1",
            ),
            _FeedEntry(
                guid="2",
                title="Second Song",
                updated="2024-01-01T12:05:00Z",
                link="http://last.fm/2",
            ),
        ]
        mock_fp_obj = _make_fp(entries)

        with patch("feedparser.parse", return_value=mock_fp_obj):
            imp.run()

        assert imp._entry_store.add_entry.call_count == 2
        titles = [c.args[2] for c in imp._entry_store.add_entry.call_args_list]
        assert "First Song" in titles
        assert "Second Song" in titles

    def test_run_strips_unpicklable_parsed_dates_from_fulldata(self):
        """updated_parsed/published_parsed are removed before being pickled via add_entry."""
        imp = self._make_importer()

        entry = _FeedEntry(
            guid="1",
            title="A Song",
            updated="2024-01-01T12:00:00Z",
            link="http://last.fm/1",
            updated_parsed=(2024, 1, 1, 12, 0, 0, 0, 1, 0),
            published_parsed=(2024, 1, 1, 12, 0, 0, 0, 1, 0),
        )
        mock_fp_obj = _make_fp([entry])

        with patch("feedparser.parse", return_value=mock_fp_obj):
            imp.run()

        _, kwargs = imp._entry_store.add_entry.call_args
        fulldata = kwargs["fulldata_json"]
        assert "updated_parsed" not in fulldata
        assert "published_parsed" not in fulldata

    def test_run_raises_on_http_error_status(self):
        """A non-2xx fetch status raises RuntimeError instead of looking like an empty feed."""
        imp = self._make_importer()
        mock_fp_obj = _make_fp([], status=503)

        with patch("feedparser.parse", return_value=mock_fp_obj):
            with pytest.raises(RuntimeError, match="HTTP 503"):
                imp.run()

        imp._entry_store.add_entry.assert_not_called()

    def test_run_raises_on_bozo_url_error(self):
        """A network failure surfaced as a bozo URLError raises RuntimeError."""
        import urllib.error

        imp = self._make_importer()
        mock_fp_obj = _make_fp(
            [],
            bozo=True,
            bozo_exception=urllib.error.URLError("connection refused"),
        )

        with patch("feedparser.parse", return_value=mock_fp_obj):
            with pytest.raises(RuntimeError, match="Failed to fetch feed"):
                imp.run()

        imp._entry_store.add_entry.assert_not_called()

    def test_run_warns_on_malformed_but_parseable_feed(self):
        """A bozo feed with recoverable entries logs a warning but still imports them."""
        imp = self._make_importer()

        entry = _FeedEntry(
            guid="1",
            title="A Song",
            updated="2024-01-01T12:00:00Z",
            link="http://last.fm/1",
        )
        mock_fp_obj = _make_fp(
            [entry], bozo=True, bozo_exception=Exception("not well-formed")
        )

        with patch("feedparser.parse", return_value=mock_fp_obj):
            imp.run()

        imp._entry_store.add_entry.assert_called_once()
