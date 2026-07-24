"""Tests for Last.fm scrobble importer."""

from unittest.mock import MagicMock, patch

from lifestream.importers.lastfm import LastfmImporter


class _FeedEntry(dict):
    """Minimal stand-in for feedparser's FeedParserDict (dict + attribute access)."""

    def __getattr__(self, name):
        try:
            return self[name]
        except KeyError:
            raise AttributeError(name)


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
        mock_fp_obj = {"entries": entries}

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
        mock_fp_obj = {"entries": [entry]}

        with patch("feedparser.parse", return_value=mock_fp_obj):
            imp.run()

        _, kwargs = imp._entry_store.add_entry.call_args
        fulldata = kwargs["fulldata_json"]
        assert "updated_parsed" not in fulldata
        assert "published_parsed" not in fulldata
