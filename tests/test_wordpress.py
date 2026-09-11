"""Tests for the WordPress importer."""

import configparser
from unittest.mock import MagicMock, patch

import pytest

from lifestream.importers.base import ConfigurationError
from lifestream.importers.wordpress import WordpressImporter


def _post(
    guid="http://example.com/?p=1",
    title="A Post",
    excerpt="",
    date_gmt="2024-03-05T09:30:00",
    link="http://example.com/a-post",
    featured_media=None,
):
    post = {
        "guid": {"rendered": guid},
        "title": {"rendered": title},
        "excerpt": {"rendered": excerpt},
        "date_gmt": date_gmt,
        "link": link,
    }
    if featured_media is not None:
        post["_embedded"] = {"wp:featuredmedia": featured_media}
    return post


def _response(posts, total_pages=1, status_code=200, text=""):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = posts
    response.headers = (
        {} if total_pages is None else {"X-WP-TotalPages": str(total_pages)}
    )
    response.text = text
    return response


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
        """A 401 response raises ConfigurationError, not silent loop exit."""
        imp = self._make_importer()
        mock_config = MagicMock()
        mock_config.get.return_value = "http://example.com"

        with (
            patch("lifestream.importers.wordpress.config", mock_config),
            patch(
                "lifestream.importers.wordpress.requests.get",
                return_value=_response([], status_code=401, text="bad creds"),
            ),
        ):
            with pytest.raises(ConfigurationError, match="Invalid credentials"):
                imp.process_site("mysite")

    def test_process_site_builds_rest_api_url_from_site_url(self):
        imp = self._make_importer()
        mock_config = MagicMock()
        mock_config.get.return_value = "http://example.com/"

        with (
            patch("lifestream.importers.wordpress.config", mock_config),
            patch(
                "lifestream.importers.wordpress.requests.get",
                return_value=_response([]),
            ) as mock_get,
        ):
            imp.process_site("mysite")

        args, kwargs = mock_get.call_args
        assert args[0] == "http://example.com/wp-json/wp/v2/posts"
        assert kwargs["auth"] == ("http://example.com/", "http://example.com/")

    def test_process_site_adds_an_entry_per_post(self):
        imp = self._make_importer()
        mock_config = MagicMock()
        mock_config.get.return_value = "http://example.com"

        posts = [
            _post(
                guid="http://example.com/?p=1",
                title="A Post",
                date_gmt="2024-03-05T09:30:00",
                link="http://example.com/a-post",
            )
        ]

        with (
            patch("lifestream.importers.wordpress.config", mock_config),
            patch(
                "lifestream.importers.wordpress.requests.get",
                return_value=_response(posts),
            ),
        ):
            imp.process_site("mysite")

        imp._entry_store.add_entry.assert_called_once()
        kwargs = imp._entry_store.add_entry.call_args.kwargs
        assert kwargs["id"] == "http://example.com/?p=1"
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
            _post(guid="g1", title="Has Title", excerpt="Ignored"),
            _post(guid="g2", title="", excerpt="Falls back to excerpt"),
            _post(guid="g3", title="", excerpt=""),
        ]

        with (
            patch("lifestream.importers.wordpress.config", mock_config),
            patch(
                "lifestream.importers.wordpress.requests.get",
                return_value=_response(posts),
            ),
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
            _post(
                guid="g1",
                title="With thumb",
                featured_media=[{"source_url": "http://img/1.jpg"}],
            ),
            _post(guid="g2", title="No embedded media at all", featured_media=None),
            _post(guid="g3", title="Empty media list", featured_media=[]),
        ]

        with (
            patch("lifestream.importers.wordpress.config", mock_config),
            patch(
                "lifestream.importers.wordpress.requests.get",
                return_value=_response(posts),
            ),
        ):
            imp.process_site("mysite")

        images = [
            call.kwargs["image"] for call in imp._entry_store.add_entry.call_args_list
        ]
        assert images == ["http://img/1.jpg", "", ""]

    def test_process_site_strips_html_from_title_and_excerpt(self):
        """title.rendered/excerpt.rendered are HTML, not plain text — markup
        and entities must not end up stored as the entry title."""
        imp = self._make_importer()
        mock_config = MagicMock()
        mock_config.get.return_value = "http://example.com"

        posts = [
            _post(guid="g1", title="It&#8217;s <em>Great</em>"),
            _post(guid="g2", title="", excerpt="<p>An excerpt</p>\n"),
        ]

        with (
            patch("lifestream.importers.wordpress.config", mock_config),
            patch(
                "lifestream.importers.wordpress.requests.get",
                return_value=_response(posts),
            ),
        ):
            imp.process_site("mysite")

        titles = [
            call.kwargs["title"] for call in imp._entry_store.add_entry.call_args_list
        ]
        assert titles == ["It’s Great", "An excerpt"]

    def test_process_site_pagination_continues_via_empty_page_when_header_missing(
        self,
    ):
        """A missing X-WP-TotalPages header must not be treated as total=1 —
        that would stop --all after a single page even with more to fetch."""
        imp = self._make_importer(["--all"])
        mock_config = MagicMock()
        mock_config.get.return_value = "http://example.com"

        page1 = [_post(guid="g1", title="Page 1 post")]
        page2 = [_post(guid="g2", title="Page 2 post")]

        with (
            patch("lifestream.importers.wordpress.config", mock_config),
            patch(
                "lifestream.importers.wordpress.requests.get",
                side_effect=[
                    _response(page1, total_pages=None),
                    _response(page2, total_pages=None),
                    _response([], total_pages=None),
                ],
            ) as mock_get,
        ):
            imp.process_site("mysite")

        assert mock_get.call_count == 3
        assert imp._entry_store.add_entry.call_count == 2

    def test_process_site_pagination_stops_at_max_pages(self):
        imp = self._make_importer(["--max_pages", "2"])
        mock_config = MagicMock()
        mock_config.get.return_value = "http://example.com"

        page1 = [_post(guid="g1", title="Page 1 post")]
        page2 = [_post(guid="g2", title="Page 2 post")]

        with (
            patch("lifestream.importers.wordpress.config", mock_config),
            patch(
                "lifestream.importers.wordpress.requests.get",
                side_effect=[
                    _response(page1, total_pages=5),
                    _response(page2, total_pages=5),
                ],
            ) as mock_get,
        ):
            imp.process_site("mysite")

        assert mock_get.call_count == 2
        assert imp._entry_store.add_entry.call_count == 2

    def test_process_site_pagination_stops_on_total_pages_header(self):
        imp = self._make_importer(["--all"])
        mock_config = MagicMock()
        mock_config.get.return_value = "http://example.com"

        page1 = [_post(guid="g1", title="Only post")]

        with (
            patch("lifestream.importers.wordpress.config", mock_config),
            patch(
                "lifestream.importers.wordpress.requests.get",
                return_value=_response(page1, total_pages=1),
            ) as mock_get,
        ):
            imp.process_site("mysite")

        assert mock_get.call_count == 1
        assert imp._entry_store.add_entry.call_count == 1

    def test_process_site_pagination_stops_on_empty_page(self):
        """Defensive: an empty page stops the loop even if the total-pages
        header is missing or wrong."""
        imp = self._make_importer(["--all"])
        mock_config = MagicMock()
        mock_config.get.return_value = "http://example.com"

        page1 = [_post(guid="g1", title="Only post")]

        with (
            patch("lifestream.importers.wordpress.config", mock_config),
            patch(
                "lifestream.importers.wordpress.requests.get",
                side_effect=[
                    _response(page1, total_pages=5),
                    _response([], total_pages=5),
                ],
            ) as mock_get,
        ):
            imp.process_site("mysite")

        assert mock_get.call_count == 2
        assert imp._entry_store.add_entry.call_count == 1
