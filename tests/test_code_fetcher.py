"""Tests for code_fetcher: the importer-CLI-process side of the OAuth
handoff with the Lifestream webserver's /keyback/ route (see
lifestream.core.webserver). The webserver is the actual HTTP listener now —
this module publishes what key it's waiting for and blocks on Redis pub/sub
until the webserver's route delivers the matching callback."""

import configparser
import json
from unittest.mock import MagicMock, patch

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


class TestGetCode:
    def test_sets_key_wanted_and_returns_matching_message(self):
        mock_cxn = MagicMock()
        mock_pubsub = MagicMock()
        mock_cxn.pubsub.return_value = mock_pubsub
        mock_pubsub.get_message.return_value = {
            "type": "message",
            "data": json.dumps({"access_token": ["abc123"]}),
        }

        with patch.object(code_fetcher, "get_redis_connection", return_value=mock_cxn):
            result = code_fetcher.get_code("access_token", timeout=5)

        assert result == {"access_token": ["abc123"]}
        mock_cxn.set.assert_called_once_with(
            code_fetcher.OAUTH_KEY_WANTED_REDIS_KEY, "access_token", ex=5
        )
        mock_pubsub.subscribe.assert_called_once_with(
            code_fetcher.OAUTH_CALLBACK_CHANNEL
        )
        mock_cxn.delete.assert_called_once_with(code_fetcher.OAUTH_KEY_WANTED_REDIS_KEY)
        mock_pubsub.close.assert_called_once()

    def test_ignores_non_message_events_and_mismatched_keys(self):
        mock_cxn = MagicMock()
        mock_pubsub = MagicMock()
        mock_cxn.pubsub.return_value = mock_pubsub
        mock_pubsub.get_message.side_effect = [
            {"type": "subscribe", "data": 1},
            {"type": "message", "data": json.dumps({"code": ["other"]})},
            {"type": "message", "data": json.dumps({"access_token": ["right"]})},
        ]

        with patch.object(code_fetcher, "get_redis_connection", return_value=mock_cxn):
            result = code_fetcher.get_code("access_token", timeout=5)

        assert result == {"access_token": ["right"]}

    def test_raises_timeout_error_when_no_message_arrives(self):
        mock_cxn = MagicMock()
        mock_pubsub = MagicMock()
        mock_cxn.pubsub.return_value = mock_pubsub
        mock_pubsub.get_message.return_value = None

        with patch.object(code_fetcher, "get_redis_connection", return_value=mock_cxn):
            with pytest.raises(TimeoutError):
                code_fetcher.get_code("access_token", timeout=0.05)

        mock_cxn.delete.assert_called_once_with(code_fetcher.OAUTH_KEY_WANTED_REDIS_KEY)
