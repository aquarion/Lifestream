"""Tests for Oyster card website importer.

The real ``mechanize`` package is not a project dependency, so it's faked
out via sys.modules rather than installed.
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

from lifestream.importers.oyster import OysterImporter

CSV_BODY = (
    "Date,Start Time,End Time,Journey/Action,Charge,Credit,Balance,Note\n"
    "01-Jan-2024,08:15,08:45,Bus journey,1.65,0.00,10.00,\n"
)


def _fake_mechanize_module(browser_instance):
    module = ModuleType("mechanize")
    module.Browser = MagicMock(return_value=browser_instance)
    module.RobustFactory = MagicMock()
    return module


class TestOysterImporter:
    def _make_importer(self, args=None):
        imp = OysterImporter()
        imp._args = imp.parse_args(args or ["gold", "1234567890"])
        imp._entry_store = MagicMock()
        imp.get_config = MagicMock(
            side_effect=lambda k, fallback=None: {
                "username": "user",
                "password": "pass",
            }.get(k, fallback)
        )
        return imp

    def test_validate_config_requires_credentials(self):
        imp = OysterImporter()
        imp.get_config = MagicMock(return_value=None)
        assert imp.validate_config() is False

    def test_run_adds_entry_from_scraped_csv(self, monkeypatch):
        imp = self._make_importer()

        browser = MagicMock()
        browser.find_link.return_value = "journey-history-link"
        html_response = MagicMock()
        html_response.read.side_effect = [
            b'<a href="/oyster/journeyDetailsPrint.do?_qv=aaa">x</a>'
            b'<a href="/oyster/journeyDetailsPrint.do?_qv=bbb">y</a>',
            CSV_BODY.encode("utf-8"),
        ]
        browser.response.return_value = html_response

        monkeypatch.setattr("lifestream.importers.oyster.sleep", lambda _: None)

        with patch.dict(sys.modules, {"mechanize": _fake_mechanize_module(browser)}):
            imp.run()

        imp._entry_store.add_entry.assert_called_once()
        args = imp._entry_store.add_entry.call_args.args
        assert args[0] == "oyster"
        assert args[2] == "Bus journey"
        assert args[4] == "2024-01-01 08:15"

        browser.open.assert_any_call("/oyster/journeyDetailsPrint.do?_qv=bbb")
