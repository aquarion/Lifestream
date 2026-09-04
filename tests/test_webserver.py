"""Tests for the Lifestream webserver (FastAPI app: CORS, health check, and
the OAuth catcher route that replaces CodeFetcher9000's dedicated listener)."""

import configparser
import json
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from lifestream.core import webserver


def _cfg(allowed_origins="https://panopticon.aquarionics.com"):
    cfg = configparser.ConfigParser()
    cfg.add_section("webserver")
    cfg.set("webserver", "allowed_origins", allowed_origins)
    return cfg


class TestAllowedOrigins:
    def test_parses_comma_separated_origins(self):
        cfg = _cfg("https://a.example.com, https://b.example.com")
        with patch.object(webserver, "config", cfg):
            assert webserver._allowed_origins() == [
                "https://a.example.com",
                "https://b.example.com",
            ]

    def test_empty_when_section_missing(self):
        cfg = configparser.ConfigParser()
        with patch.object(webserver, "config", cfg):
            assert webserver._allowed_origins() == []


class TestHealth:
    def test_health_returns_ok(self):
        with patch.object(webserver, "config", _cfg()):
            app = webserver.create_app()
        client = TestClient(app)

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_cors_header_present_for_allowed_origin(self):
        with patch.object(
            webserver, "config", _cfg("https://panopticon.aquarionics.com")
        ):
            app = webserver.create_app()
        client = TestClient(app)

        response = client.get(
            "/health", headers={"Origin": "https://panopticon.aquarionics.com"}
        )

        assert (
            response.headers["access-control-allow-origin"]
            == "https://panopticon.aquarionics.com"
        )

    def test_cors_header_absent_for_disallowed_origin(self):
        with patch.object(
            webserver, "config", _cfg("https://panopticon.aquarionics.com")
        ):
            app = webserver.create_app()
        client = TestClient(app)

        response = client.get("/health", headers={"Origin": "https://evil.example.com"})

        assert "access-control-allow-origin" not in response.headers


class TestKeyback:
    def _app(self):
        with patch.object(webserver, "config", _cfg()):
            return webserver.create_app()

    def test_matching_key_publishes_and_serves_success_page(self):
        client = TestClient(self._app())
        mock_cxn = MagicMock()
        mock_cxn.get.return_value = b"access_token"

        with patch.object(webserver, "get_redis_connection", return_value=mock_cxn):
            response = client.get("/keyback/?access_token=abc123")

        assert response.status_code == 200
        assert "Sorry" not in response.text
        mock_cxn.publish.assert_called_once()
        channel, payload = mock_cxn.publish.call_args.args
        assert channel == webserver.OAUTH_CALLBACK_CHANNEL
        assert json.loads(payload) == {"access_token": ["abc123"]}

    def test_non_matching_key_serves_failure_page_with_substitution(self):
        client = TestClient(self._app())
        mock_cxn = MagicMock()
        mock_cxn.get.return_value = b"access_token"

        with patch.object(webserver, "get_redis_connection", return_value=mock_cxn):
            response = client.get("/keyback/?error=access_denied")

        assert response.status_code == 200
        assert "Sorry" in response.text
        assert "error" in response.text
        assert "access_token" in response.text
        mock_cxn.publish.assert_not_called()

    def test_no_key_wanted_in_redis_serves_failure_page(self):
        client = TestClient(self._app())
        mock_cxn = MagicMock()
        mock_cxn.get.return_value = None

        with patch.object(webserver, "get_redis_connection", return_value=mock_cxn):
            response = client.get("/keyback/?access_token=abc123")

        assert response.status_code == 200
        assert "Sorry" in response.text
        mock_cxn.publish.assert_not_called()


class TestTestSuccessRoute:
    def test_serves_success_page_unconditionally(self):
        with patch.object(webserver, "config", _cfg()):
            app = webserver.create_app()
        client = TestClient(app)

        response = client.get("/test/success")

        assert response.status_code == 200
        assert "Sorry" not in response.text
