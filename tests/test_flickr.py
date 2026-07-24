"""Tests for Flickr photo importer."""

from unittest.mock import MagicMock, patch

from lifestream.importers.flickr import FlickrImporter


class TestFlickrImporter:
    def _make_importer(self):
        imp = FlickrImporter()
        imp._args = imp.parse_args([])
        imp.get_config = MagicMock(return_value="testvalue")
        return imp

    def test_run_skips_db_lookup_in_no_db_mode(self):
        """In no-db mode, run() must not touch entry_store.dbcxn at all."""
        imp = self._make_importer()
        imp._entry_store = MagicMock()
        imp._entry_store.no_db = True

        mock_photos_el = MagicMock()
        mock_photos_el.attrib = {"pages": "0"}
        mock_photos_xml = MagicMock()
        mock_photos_xml.find.return_value = mock_photos_el

        mock_flickr = MagicMock()
        mock_flickr.photos_search.return_value = mock_photos_xml

        with patch("flickrapi.FlickrAPI", return_value=mock_flickr):
            imp.run()

        imp._entry_store.dbcxn.cursor.assert_not_called()

    def test_run_uses_cursor_context_manager_for_since_lookup(self):
        """When not in no-db mode, the 'since' timestamp is read via a cursor context manager."""
        imp = self._make_importer()
        imp._entry_store = MagicMock()
        imp._entry_store.no_db = False

        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (1_700_000_000,)
        mock_cursor.__enter__ = MagicMock(return_value=mock_cursor)
        mock_cursor.__exit__ = MagicMock(return_value=False)
        imp._entry_store.dbcxn.cursor.return_value = mock_cursor

        mock_photos_el = MagicMock()
        mock_photos_el.attrib = {"pages": "0"}
        mock_photos_xml = MagicMock()
        mock_photos_xml.find.return_value = mock_photos_el

        mock_flickr = MagicMock()
        mock_flickr.photos_search.return_value = mock_photos_xml

        with patch("flickrapi.FlickrAPI", return_value=mock_flickr):
            imp.run()

        mock_cursor.execute.assert_called_once()
        # The since value from the cursor is passed through to the Flickr search.
        _, kwargs = mock_flickr.photos_search.call_args
        assert kwargs["min_taken_date"] == 1_700_000_000

    def test_run_returns_early_when_no_pages(self):
        """pages == 0 short-circuits before any pagination/entry_store calls."""
        imp = self._make_importer()
        imp._entry_store = MagicMock()
        imp._entry_store.no_db = True

        mock_photos_el = MagicMock()
        mock_photos_el.attrib = {"pages": "0"}
        mock_photos_xml = MagicMock()
        mock_photos_xml.find.return_value = mock_photos_el

        mock_flickr = MagicMock()
        mock_flickr.photos_search.return_value = mock_photos_xml

        with patch("flickrapi.FlickrAPI", return_value=mock_flickr):
            imp.run()

        imp._entry_store.add_entry.assert_not_called()
        # Only the initial pages-check search call, no per-page fetch.
        assert mock_flickr.photos_search.call_count == 1
