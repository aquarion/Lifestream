"""Tests for the Lifestream webserver (FastAPI app: CORS, health check, and
the OAuth catcher route that replaces CodeFetcher9000's dedicated listener)."""

import configparser
from unittest.mock import patch

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
