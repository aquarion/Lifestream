"""Tests for Instagram importer.

The real ``InstagramAPI`` package is unofficial/unmaintained and not a
project dependency, so it's faked out via sys.modules rather than installed.
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from lifestream.importers.base import ConfigurationError
from lifestream.importers.instagram import InstagramImporter


def _fake_instagram_module(api_instance):
    module = ModuleType("InstagramAPI")
    module.InstagramAPI = MagicMock(return_value=api_instance)
    return module


class TestInstagramImporter:
    def _make_importer(self, args=None):
        imp = InstagramImporter()
        imp._args = imp.parse_args(args or [])
        imp._entry_store = MagicMock()
        imp.get_config = MagicMock(return_value="testuser")
        return imp

    def test_validate_config_requires_credentials(self):
        imp = InstagramImporter()
        imp.get_config = MagicMock(return_value=None)
        assert imp.validate_config() is False

    def test_run_raises_on_login_failure(self):
        imp = self._make_importer()
        api = MagicMock()
        api.login.return_value = False

        with patch.dict(sys.modules, {"InstagramAPI": _fake_instagram_module(api)}):
            with pytest.raises(ConfigurationError, match="login failed"):
                imp.run()

    def test_run_adds_entry_per_feed_item(self):
        imp = self._make_importer()
        api = MagicMock()
        api.login.return_value = True
        api.getSelfUserFeed.return_value = [
            {
                "id": "1",
                "caption": {"text": "hello"},
                "taken_at": 1_700_000_000,
                "code": "abc123",
                "image_versions2": {
                    "candidates": [{"url": "https://img.example/1.jpg"}]
                },
            }
        ]

        with patch.dict(sys.modules, {"InstagramAPI": _fake_instagram_module(api)}):
            imp.run()

        imp._entry_store.add_entry.assert_called_once()
        args = imp._entry_store.add_entry.call_args.args
        assert args[0] == "photo"
        assert args[1] == "1"
        assert args[2] == "hello"
        assert args[3] == "instagram"

    def test_run_raises_when_feed_fetch_fails(self):
        imp = self._make_importer()
        api = MagicMock()
        api.login.return_value = True
        api.getSelfUserFeed.return_value = None

        with patch.dict(sys.modules, {"InstagramAPI": _fake_instagram_module(api)}):
            with pytest.raises(
                ConfigurationError, match="Failed to get Instagram feed"
            ):
                imp.run()
