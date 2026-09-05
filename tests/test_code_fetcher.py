"""Tests for code_fetcher: the importer-CLI-process side of the OAuth
handoff with the Lifestream webserver's /keyback/ route (see
lifestream.core.webserver). The webserver is the actual HTTP listener now —
this module publishes what key it's waiting for and blocks on Redis pub/sub
until the webserver's route delivers the matching callback."""

import configparser
import itertools
import json
from unittest.mock import MagicMock, call, patch

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
        mock_cxn.get.return_value = None
        mock_pubsub = MagicMock()
        mock_cxn.pubsub.return_value = mock_pubsub
        mock_pubsub.get_message.side_effect = [
            {"type": "subscribe", "data": 1},
            {"type": "message", "data": json.dumps({"access_token": ["abc123"]})},
        ]

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
        mock_cxn.get.return_value = None
        mock_pubsub = MagicMock()
        mock_cxn.pubsub.return_value = mock_pubsub
        mock_pubsub.get_message.side_effect = [
            {"type": "subscribe", "data": 1},
            {"type": "subscribe", "data": 1},
            {"type": "message", "data": json.dumps({"code": ["other"]})},
            {"type": "message", "data": json.dumps({"access_token": ["right"]})},
        ]

        with patch.object(code_fetcher, "get_redis_connection", return_value=mock_cxn):
            result = code_fetcher.get_code("access_token", timeout=5)

        assert result == {"access_token": ["right"]}

    def test_ignores_malformed_json_messages(self):
        """Regression: a stray non-JSON publish on the shared channel must not
        crash the wait loop — it should be logged and skipped."""
        mock_cxn = MagicMock()
        mock_cxn.get.return_value = None
        mock_pubsub = MagicMock()
        mock_cxn.pubsub.return_value = mock_pubsub
        mock_pubsub.get_message.side_effect = [
            {"type": "subscribe", "data": 1},
            {"type": "message", "data": "not valid json{{{"},
            {"type": "message", "data": json.dumps({"access_token": ["right"]})},
        ]

        with patch.object(code_fetcher, "get_redis_connection", return_value=mock_cxn):
            result = code_fetcher.get_code("access_token", timeout=5)

        assert result == {"access_token": ["right"]}

    def test_raises_timeout_error_when_no_message_arrives(self):
        mock_cxn = MagicMock()
        mock_cxn.get.return_value = None
        mock_pubsub = MagicMock()
        mock_cxn.pubsub.return_value = mock_pubsub
        mock_pubsub.get_message.side_effect = itertools.chain(
            [{"type": "subscribe", "data": 1}], itertools.repeat(None)
        )

        with patch.object(code_fetcher, "get_redis_connection", return_value=mock_cxn):
            with pytest.raises(TimeoutError):
                code_fetcher.get_code("access_token", timeout=0.05)

        mock_cxn.delete.assert_called_once_with(code_fetcher.OAUTH_KEY_WANTED_REDIS_KEY)

    def test_raises_runtime_error_when_another_flow_already_in_progress(self):
        """Regression: a second concurrent get_code() call must not silently
        clobber the first flow's key_wanted — it should refuse to start."""
        mock_cxn = MagicMock()
        mock_cxn.get.return_value = b"code"

        with patch.object(code_fetcher, "get_redis_connection", return_value=mock_cxn):
            with pytest.raises(RuntimeError):
                code_fetcher.get_code("access_token", timeout=5)

        mock_cxn.set.assert_not_called()

    def test_subscribes_and_confirms_before_setting_key_wanted(self):
        """Regression: subscribe (and its confirmation) must happen before
        the key is advertised in Redis, or a callback could be published
        with nobody listening yet and be lost."""
        mock_cxn = MagicMock()
        mock_cxn.get.return_value = None
        mock_pubsub = MagicMock()
        mock_cxn.pubsub.return_value = mock_pubsub
        mock_pubsub.get_message.side_effect = [
            {"type": "subscribe", "data": 1},
            {"type": "message", "data": json.dumps({"access_token": ["abc123"]})},
        ]

        manager = MagicMock()
        manager.attach_mock(mock_pubsub.subscribe, "subscribe")
        manager.attach_mock(mock_pubsub.get_message, "get_message")
        manager.attach_mock(mock_cxn.set, "set")

        with patch.object(code_fetcher, "get_redis_connection", return_value=mock_cxn):
            code_fetcher.get_code("access_token", timeout=5)

        call_names = [c[0] for c in manager.mock_calls]
        assert call_names.index("subscribe") < call_names.index("set")
        assert call_names.index("get_message") < call_names.index("set")

    def test_raises_timeout_error_when_subscribe_confirmation_never_arrives(self):
        """Regression: the confirmation wait must be bounded independently of
        the overall timeout (not reuse the full budget), and since set() is
        never reached on this path, the key must NOT be deleted — it could
        belong to a different flow that got set in the meantime."""
        mock_cxn = MagicMock()
        mock_cxn.get.return_value = None
        mock_pubsub = MagicMock()
        mock_cxn.pubsub.return_value = mock_pubsub
        mock_pubsub.get_message.return_value = None

        with patch.object(code_fetcher, "get_redis_connection", return_value=mock_cxn):
            with pytest.raises(TimeoutError):
                code_fetcher.get_code("access_token", timeout=60)

        mock_pubsub.get_message.assert_called_once_with(
            timeout=code_fetcher.SUBSCRIBE_CONFIRMATION_TIMEOUT_SECONDS
        )
        mock_cxn.set.assert_not_called()
        mock_cxn.delete.assert_not_called()
        mock_pubsub.close.assert_called_once()

    def test_wait_loop_bounds_get_message_timeout_by_remaining_time(self):
        """Regression: each get_message() call in the wait loop must be capped
        by whatever time is actually left before the deadline, not always
        wait a full 1.0s — otherwise a small remaining budget gets rounded up
        to a full second, overshooting the documented overall timeout."""
        mock_cxn = MagicMock()
        mock_cxn.get.return_value = None
        mock_pubsub = MagicMock()
        mock_cxn.pubsub.return_value = mock_pubsub
        mock_pubsub.get_message.side_effect = [
            {"type": "subscribe", "data": 1},
            None,
        ]

        with patch.object(code_fetcher, "get_redis_connection", return_value=mock_cxn):
            with patch.object(
                code_fetcher.time, "monotonic", side_effect=[100.0, 104.5, 106.0]
            ):
                with pytest.raises(TimeoutError):
                    code_fetcher.get_code("access_token", timeout=5)

        wait_loop_call = mock_pubsub.get_message.call_args_list[1]
        assert wait_loop_call == call(timeout=0.5)
