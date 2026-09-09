"""Tests for the WordPress importer."""

import configparser
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from lifestream.importers.base import ConfigurationError
from lifestream.importers.wordpress import WordpressImporter


class FakePost:
    """Stand-in for a wordpress_xmlrpc WordPressPost."""

    def __init__(self, guid, title="", excerpt="", thumbnail=None, date=None, link=""):
        self.guid = guid
        self.title = title
        self.excerpt = excerpt
        self.thumbnail = thumbnail
        self.date = date or datetime(2024, 1, 1, 12, 0)
        self.link = link


class TestWordpressImporter:
    def _make_importer(self, args=None):
        imp = WordpressImporter()
        imp._args = imp.parse_args(args or [])
        imp._entry_store = MagicMock()
        return imp

    def test_process_site_raises_on_missing_section(self):
        """Missing config section raises ConfigurationError, not silent return."""
        imp = self._make_importer()
        mock_config = MagicMock()
        mock_config.get.side_effect = configparser.NoSectionError("wordpress:missing")

        with patch("lifestream.importers.wordpress.config", mock_config):
            with pytest.raises(ConfigurationError, match="wordpress:missing"):
                imp.process_site("missing")

    def test_process_site_raises_on_invalid_credentials(self):
        """Invalid credentials raise ConfigurationError, not silent loop exit."""
        from wordpress_xmlrpc import exceptions as wp_exc

        imp = self._make_importer()
        mock_config = MagicMock()
        mock_config.get.return_value = "http://example.com"

        mock_client = MagicMock()
        mock_client.call.side_effect = wp_exc.InvalidCredentialsError()

        with patch("lifestream.importers.wordpress.config", mock_config):
            with patch(
                "lifestream.importers.wordpress.Client", return_value=mock_client
            ):
                with pytest.raises(ConfigurationError, match="Invalid credentials"):
                    imp.process_site("mysite")

    def test_process_site_adds_an_entry_per_post(self):
        imp = self._make_importer()
        mock_config = MagicMock()
        mock_config.get.return_value = "http://example.com"

        posts = [
            FakePost(
                "guid-1",
                title="A Post",
                date=datetime(2024, 3, 5, 9, 30),
                link="http://example.com/a-post",
            ),
        ]
        mock_client = MagicMock()
        mock_client.call.side_effect = [posts, []]

        with (
            patch("lifestream.importers.wordpress.config", mock_config),
            patch("lifestream.importers.wordpress.Client", return_value=mock_client),
        ):
            imp.process_site("mysite")

        imp._entry_store.add_entry.assert_called_once()
        kwargs = imp._entry_store.add_entry.call_args.kwargs
        assert kwargs["id"] == "guid-1"
        assert kwargs["title"] == "A Post"
        assert kwargs["source"] == "mysite"
        assert kwargs["date"] == "2024-03-05 09:30"
        assert kwargs["url"] == "http://example.com/a-post"
        assert kwargs["image"] == ""
        assert kwargs["type"] == "wordpress"

    def test_process_site_title_fallback_chain(self):
        imp = self._make_importer()
        mock_config = MagicMock()
        mock_config.get.return_value = "http://example.com"

        posts = [
            FakePost("g1", title="Has Title", excerpt="Ignored"),
            FakePost("g2", title="", excerpt="Falls back to excerpt"),
            FakePost("g3", title="", excerpt=""),
        ]
        mock_client = MagicMock()
        mock_client.call.side_effect = [posts, []]

        with (
            patch("lifestream.importers.wordpress.config", mock_config),
            patch("lifestream.importers.wordpress.Client", return_value=mock_client),
        ):
            imp.process_site("mysite")

        titles = [
            call.kwargs["title"] for call in imp._entry_store.add_entry.call_args_list
        ]
        assert titles == ["Has Title", "Falls back to excerpt", "[Untitled Post]"]

    def test_process_site_thumbnail_extraction(self):
        imp = self._make_importer()
        mock_config = MagicMock()
        mock_config.get.return_value = "http://example.com"

        posts = [
            FakePost("g1", title="With thumb", thumbnail={"link": "http://img/1.jpg"}),
            FakePost("g2", title="Thumb with no link key", thumbnail={"foo": "bar"}),
            FakePost("g3", title="No thumb", thumbnail=None),
        ]
        mock_client = MagicMock()
        mock_client.call.side_effect = [posts, []]

        with (
            patch("lifestream.importers.wordpress.config", mock_config),
            patch("lifestream.importers.wordpress.Client", return_value=mock_client),
        ):
            imp.process_site("mysite")

        images = [
            call.kwargs["image"] for call in imp._entry_store.add_entry.call_args_list
        ]
        assert images == ["http://img/1.jpg", "", ""]

    def test_process_site_pagination_stops_at_max_pages(self):
        imp = self._make_importer(["--max_pages", "2"])
        mock_config = MagicMock()
        mock_config.get.return_value = "http://example.com"

        page1 = [FakePost("g1", title="Page 1 post")]
        page2 = [FakePost("g2", title="Page 2 post")]
        # A third call would mean pagination overran max_pages.
        mock_client = MagicMock()
        mock_client.call.side_effect = [
            page1,
            page2,
            RuntimeError("should not be called"),
        ]

        with (
            patch("lifestream.importers.wordpress.config", mock_config),
            patch("lifestream.importers.wordpress.Client", return_value=mock_client),
        ):
            imp.process_site("mysite")

        assert mock_client.call.call_count == 2
        assert imp._entry_store.add_entry.call_count == 2

    def test_process_site_pagination_stops_on_empty_page(self):
        imp = self._make_importer(["--all"])
        mock_config = MagicMock()
        mock_config.get.return_value = "http://example.com"

        page1 = [FakePost("g1", title="Only post")]
        mock_client = MagicMock()
        mock_client.call.side_effect = [page1, []]

        with (
            patch("lifestream.importers.wordpress.config", mock_config),
            patch("lifestream.importers.wordpress.Client", return_value=mock_client),
        ):
            imp.process_site("mysite")

        assert mock_client.call.call_count == 2
        assert imp._entry_store.add_entry.call_count == 1
