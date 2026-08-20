"""Tests for the CodeFetcher9000 OAuth callback helper."""

import configparser
from unittest.mock import mock_open, patch

import pytest

from lifestream.core import code_fetcher


class TestGetUrl:
    def test_get_url_builds_https_keyback_url(self):
        cfg = configparser.ConfigParser()
        cfg.add_section("CodeFetcher9000")
        cfg.set("CodeFetcher9000", "domain", "example.com")
        cfg.set("CodeFetcher9000", "port", "2871")

        with patch("lifestream.core.code_fetcher.config", cfg):
            assert code_fetcher.get_url() == "https://example.com:2871/keyback/"


class TestAreWeWorking:
    def test_raises_we_say_not_today_when_not_configured(self):
        cfg = configparser.ConfigParser()
        with patch("lifestream.core.code_fetcher.config", cfg):
            with pytest.raises(code_fetcher.WeSayNotToday):
                code_fetcher.are_we_working()

    def test_raises_we_say_not_today_when_cert_file_missing(self):
        cfg = configparser.ConfigParser()
        cfg.add_section("CodeFetcher9000")
        cfg.set("CodeFetcher9000", "certfile", "/nonexistent/cert.pem")
        cfg.set("CodeFetcher9000", "keyfile", "/nonexistent/key.pem")

        with patch("lifestream.core.code_fetcher.config", cfg):
            with pytest.raises(code_fetcher.WeSayNotToday):
                code_fetcher.are_we_working()

    def test_returns_true_when_cert_and_key_readable(self):
        cfg = configparser.ConfigParser()
        cfg.add_section("CodeFetcher9000")
        cfg.set("CodeFetcher9000", "certfile", "/fake/cert.pem")
        cfg.set("CodeFetcher9000", "keyfile", "/fake/key.pem")

        with (
            patch("lifestream.core.code_fetcher.config", cfg),
            patch("builtins.open", mock_open(read_data=b"data")),
        ):
            assert code_fetcher.are_we_working() is True
