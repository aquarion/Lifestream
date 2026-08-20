"""Tests for FFXIV Lodestone achievements importer."""

from datetime import datetime
from unittest.mock import MagicMock

import pytest

from lifestream.importers.base import ConfigurationError
from lifestream.importers.ffxiv import ACHIEVEMENT_SELECTORS, FFXIVImporter, Lodestone


class TestFFXIVImporter:
    def _make_importer(self, args=None):
        imp = FFXIVImporter()
        imp._args = imp.parse_args(args or [])
        imp._entry_store = MagicMock()
        imp.get_config = MagicMock(
            side_effect=lambda k, fallback=None: {
                "achievement_db": "/tmp/fake.db",
                "characters": "111,222",
                "icon_base": "https://icons.example.com/",
            }.get(k, fallback)
        )
        return imp

    def test_validate_config_requires_all_keys(self):
        imp = FFXIVImporter()
        imp.get_config = MagicMock(return_value=None)
        assert imp.validate_config() is False

    def test_run_updates_achievements_for_each_character(self, monkeypatch):
        """One character's worth of achievements is fetched and stored per configured character."""
        imp = self._make_importer()

        lodestone_instances = []

        class FakeLodestone:
            def __init__(self, *_args, **_kwargs):
                lodestone_instances.append(self)

            def get_achievements(self, char_id):
                return [
                    {
                        "Name": "Achievement",
                        "ID": "42",
                        "Icon": "000000/000042.png",
                        "Date": datetime(2024, 1, 1),
                    }
                ]

            def get_character_info(self, char_id):
                return {"Name": f"Char-{char_id}"}

        monkeypatch.setattr("lifestream.importers.ffxiv.Lodestone", FakeLodestone)

        imp.run()

        assert imp._entry_store.add_entry.call_count == 2
        first_call = imp._entry_store.add_entry.call_args_list[0].kwargs
        assert first_call["id"] == "ffxiv-111-42"
        assert "Char-111" in first_call["title"]
        assert first_call["image"] == "https://icons.example.com/000000/000042.png"

    def test_load_selector_map_raises_configuration_error_when_missing(self):
        """Missing lodestone-css-selectors submodule data fails clearly, not
        with a bare FileNotFoundError."""
        lodestone = Lodestone.__new__(Lodestone)
        with pytest.raises(ConfigurationError, match="submodule"):
            lodestone._load_selector_map(ACHIEVEMENT_SELECTORS)

    def test_get_achievements_refuses_off_site_next_link(self):
        """A scraped 'next page' link must stay on finalfantasyxiv.com."""
        lodestone = Lodestone.__new__(Lodestone)
        lodestone.max_pages = 5
        lodestone.all_achievements = False
        lodestone.get_character_detail = MagicMock(return_value="<html></html>")

        def fake_parse(_html):
            lodestone.next = "https://evil.example.com/steal-cookies"
            return []

        lodestone.parse_achievements_page = MagicMock(side_effect=fake_parse)

        with pytest.raises(ValueError, match="off-site"):
            lodestone.get_achievements("1")

    def test_run_handles_missing_icon(self, monkeypatch):
        """An achievement with no resolved icon still gets stored, with an empty image."""
        imp = self._make_importer(["--max-pages", "1"])

        class FakeLodestone:
            def __init__(self, *_args, **_kwargs):
                pass

            def get_achievements(self, char_id):
                return [
                    {
                        "Name": "No Icon",
                        "ID": "1",
                        "Icon": None,
                        "Date": datetime(2024, 1, 1),
                    }
                ]

            def get_character_info(self, char_id):
                return {"Name": "Someone"}

        monkeypatch.setattr("lifestream.importers.ffxiv.Lodestone", FakeLodestone)

        imp.run()

        calls = imp._entry_store.add_entry.call_args_list
        assert calls[0].kwargs["image"] == ""
