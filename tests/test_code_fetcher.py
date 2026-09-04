"""Tests for code_fetcher: the importer-CLI-process side of the OAuth
handoff with the Lifestream webserver's /keyback/ route (see
lifestream.core.webserver). The webserver is the actual HTTP listener now —
this module publishes what key it's waiting for and blocks on Redis pub/sub
until the webserver's route delivers the matching callback."""

import configparser
from unittest.mock import patch

import pytest

from lifestream.core import code_fetcher


def _cfg(domain="example.com"):
    cfg = configparser.ConfigParser()
    cfg.add_section("webserver")
    if domain is not None:
        cfg.set("webserver", "domain", domain)
    return cfg


class TestGetUrl:
    def test_get_url_builds_https_keyback_url(self):
        with patch.object(code_fetcher, "config", _cfg("example.com")):
            assert code_fetcher.get_url() == "https://example.com/keyback/"


class TestAreWeWorking:
    def test_raises_we_say_not_today_when_not_configured(self):
        cfg = configparser.ConfigParser()
        with patch.object(code_fetcher, "config", cfg):
            with pytest.raises(code_fetcher.WeSayNotToday):
                code_fetcher.are_we_working()

    def test_returns_true_when_domain_configured(self):
        with patch.object(code_fetcher, "config", _cfg("example.com")):
            assert code_fetcher.are_we_working() is True
