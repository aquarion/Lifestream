"""Tests for AT Protocol (Bluesky) posts importer."""

import configparser
from unittest.mock import MagicMock, patch

import pytest

from lifestream.importers.atproto_posts import AtprotoImporter
from lifestream.importers.base import ConfigurationError


@pytest.fixture
def fake_config():
    cfg = configparser.ConfigParser()
    cfg.add_section("atproto:example.com")
    cfg.set("atproto:example.com", "username", "user")
    cfg.set("atproto:example.com", "password", "pass")
    cfg.set("atproto:example.com", "handle", "user.example.com")
    with patch("lifestream.importers.atproto_posts.config", cfg):
        yield cfg


class TestAtprotoImporter:
    def _make_importer(self, args=None):
        imp = AtprotoImporter()
        imp._args = imp.parse_args(args or [])
        imp._entry_store = MagicMock()
        return imp

    def test_get_sites_discovers_atproto_sections(self, fake_config):
        imp = self._make_importer()
        assert imp._get_sites() == ["example.com"]

    def test_get_sites_prefers_explicit_site_arg(self, fake_config):
        imp = self._make_importer(["--site", "other.com"])
        assert imp._get_sites() == ["other.com"]

    def test_get_sites_ignores_bare_atproto_section(self):
        """A literal [atproto] section (no ':site' suffix) must not IndexError."""
        cfg = configparser.ConfigParser()
        cfg.add_section("atproto")
        cfg.add_section("atproto:example.com")
        with patch("lifestream.importers.atproto_posts.config", cfg):
            imp = self._make_importer()
            assert imp._get_sites() == ["example.com"]

    def test_validate_config_fails_with_no_sites(self):
        empty_cfg = configparser.ConfigParser()
        with patch("lifestream.importers.atproto_posts.config", empty_cfg):
            imp = self._make_importer()
            assert imp.validate_config() is False

    def test_process_site_raises_configuration_error_for_missing_section(
        self, fake_config
    ):
        imp = self._make_importer()
        with pytest.raises(ConfigurationError):
            imp._process_site("unknown.com")

    def test_process_post_skips_reply(self, fake_config):
        imp = self._make_importer()
        item = MagicMock()
        item.post.author.handle = "user.example.com"
        item.post.record.reply = MagicMock()

        imp._process_post(item, "example.com", "user.example.com")

        imp._entry_store.add_entry.assert_not_called()

    def test_process_post_skips_other_authors(self, fake_config):
        imp = self._make_importer()
        item = MagicMock()
        item.post.author.handle = "someone.else"

        imp._process_post(item, "example.com", "user.example.com")

        imp._entry_store.add_entry.assert_not_called()

    def test_run_paginates_until_no_more_posts(self, fake_config):
        """process_site stops once a page comes back with no feed items."""
        imp = self._make_importer(["--max_pages", "5"])

        atserver = MagicMock()
        first_page = MagicMock(cursor="page2", feed=[])
        atserver.get_author_feed.return_value = first_page

        with patch(
            "lifestream.importers.atproto_posts.AtClient", return_value=atserver
        ):
            imp._process_site("example.com")

        atserver.login.assert_called_once_with("user", "pass")
        assert atserver.get_author_feed.call_count == 1
