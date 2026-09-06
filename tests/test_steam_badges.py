"""Tests for the Steam badges importer."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from lifestream.importers.steam_badges import SteamBadgesImporter

BADGE_ROW_WITH_YEAR = """
<div id="badge_badge_1" class="badge_row is_link">
  <a class="badge_row_overlay" href="https://steamcommunity.com/id/gaben/badges/1"></a>
  <div class="badge_row_inner">
    <div class="badge_info">
      <div class="badge_info_image">
        <img src="trans.gif" data-delayed-image="https://example.com/icon1.png" class="badge_icon">
      </div>
      <div class="badge_info_description">
        <div class="badge_info_title">Years of Service</div>
        <div class="badge_info_unlocked">
          Unlocked Feb 15, 2025 @ 11:04pm
        </div>
      </div>
    </div>
  </div>
</div>
"""

BADGE_ROW_WITHOUT_YEAR = """
<div id="badge_badge_13" class="badge_row is_link">
  <a class="badge_row_overlay" href="https://steamcommunity.com/id/gaben/badges/13"></a>
  <div class="badge_row_inner">
    <div class="badge_info">
      <div class="badge_info_image">
        <img src="trans.gif" data-delayed-image="https://example.com/icon13.png" class="badge_icon">
      </div>
      <div class="badge_info_description">
        <div class="badge_info_title">Sharp-Eyed Stockpiler</div>
        <div class="badge_info_unlocked">
          Unlocked Aug 8 @ 5:18pm
        </div>
      </div>
    </div>
  </div>
</div>
"""

BADGE_ROW_IN_PROGRESS = """
<div id="badge_badge_99" class="badge_row">
  <div class="badge_row_inner">
    <div class="badge_info">
      <div class="badge_info_image">
        <img src="trans.gif" class="badge_icon">
      </div>
      <div class="badge_info_description">
        <div class="badge_info_title">Not Yet Unlocked</div>
      </div>
    </div>
  </div>
</div>
"""

BADGE_ROW_NO_LINK = """
<div id="badge_badge_5" class="badge_row">
  <div class="badge_row_inner">
    <div class="badge_info">
      <div class="badge_info_image">
        <img src="trans.gif" data-delayed-image="https://example.com/icon5.png" class="badge_icon">
      </div>
      <div class="badge_info_description">
        <div class="badge_info_title">No Link Badge</div>
        <div class="badge_info_unlocked">
          Unlocked Jan 1 @ 12:00am
        </div>
      </div>
    </div>
  </div>
</div>
"""


class TestSteamBadgesImporter:
    def _make_importer(self):
        imp = SteamBadgesImporter()
        imp._args = imp.parse_args([])
        imp._entry_store = MagicMock()
        return imp

    def test_validate_config_fails_when_username_missing(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value=None)
        assert imp.validate_config() is False

    def test_validate_config_passes_when_username_present(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value="gaben")
        assert imp.validate_config() is True

    def test_fetch_badges_page_returns_response_text(self):
        imp = self._make_importer()
        response = MagicMock()
        response.text = "<html>ok</html>"

        with patch(
            "lifestream.importers.steam_badges.requests.get", return_value=response
        ) as mock_get:
            result = imp.fetch_badges_page("gaben")

        assert result == "<html>ok</html>"
        mock_get.assert_called_once_with(
            "https://steamcommunity.com/id/gaben/badges",
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=30,
        )

    def test_parse_unlocked_date_with_year(self):
        imp = SteamBadgesImporter
        dt = imp._parse_unlocked_date("Unlocked Feb 15, 2025 @ 11:04pm")
        assert dt.tzinfo is not None
        assert dt.astimezone(timezone.utc).year == 2025

    def test_parse_unlocked_date_without_year_uses_current_year(self):
        dt = SteamBadgesImporter._parse_unlocked_date("Aug 8 @ 5:18pm")
        assert dt.year == datetime.now().year

    def test_parse_badges_extracts_title_image_url_and_date_text(self):
        imp = self._make_importer()

        badges = imp.parse_badges(
            BADGE_ROW_WITH_YEAR, fallback_url="https://fallback.example/badges"
        )

        assert len(badges) == 1
        badge = badges[0]
        assert badge["title"] == "Years of Service"
        assert badge["image"] == "https://example.com/icon1.png"
        assert badge["url"] == "https://steamcommunity.com/id/gaben/badges/1"
        assert badge["unlocked_text"] == "Unlocked Feb 15, 2025 @ 11:04pm"

    def test_parse_badges_skips_rows_with_no_unlocked_date(self):
        imp = self._make_importer()

        badges = imp.parse_badges(
            BADGE_ROW_IN_PROGRESS, fallback_url="https://fallback.example/badges"
        )

        assert badges == []

    def test_parse_badges_falls_back_to_list_url_when_no_link(self):
        imp = self._make_importer()

        badges = imp.parse_badges(
            BADGE_ROW_NO_LINK, fallback_url="https://fallback.example/badges"
        )

        assert len(badges) == 1
        assert badges[0]["url"] == "https://fallback.example/badges"

    def test_parse_badges_handles_multiple_rows(self):
        imp = self._make_importer()
        html = BADGE_ROW_WITH_YEAR + BADGE_ROW_WITHOUT_YEAR

        badges = imp.parse_badges(html, fallback_url="https://fallback.example/badges")

        assert [b["title"] for b in badges] == [
            "Years of Service",
            "Sharp-Eyed Stockpiler",
        ]

    def test_badge_entry_id_differs_for_same_title_different_dates(self):
        """Regression: repeated badges with the same title (e.g. "Years of
        Service") must not collapse into a single entry id."""
        id_2024 = SteamBadgesImporter._badge_entry_id(
            "Years of Service", "Unlocked Jan 1, 2024 @ 12:00am"
        )
        id_2025 = SteamBadgesImporter._badge_entry_id(
            "Years of Service", "Unlocked Jan 1, 2025 @ 12:00am"
        )
        assert id_2024 != id_2025

    def test_process_badge_adds_entry(self):
        imp = self._make_importer()
        badge = {
            "title": "Years of Service",
            "unlocked_text": "Unlocked Feb 15, 2025 @ 11:04pm",
            "image": "https://example.com/icon1.png",
            "url": "https://steamcommunity.com/id/gaben/badges/1",
        }

        imp.process_badge(badge)

        imp._entry_store.add_entry.assert_called_once()
        args, kwargs = imp._entry_store.add_entry.call_args
        assert args[0] == "badge"
        assert args[2] == "Years of Service"
        assert args[3] == "steam"
        assert kwargs["url"] == "https://steamcommunity.com/id/gaben/badges/1"
        assert kwargs["image"] == "https://example.com/icon1.png"

    def test_process_badge_skips_unparseable_date_without_raising(self):
        imp = self._make_importer()
        badge = {
            "title": "Weird Badge",
            "unlocked_text": "not a date",
            "image": "",
            "url": "https://example.com",
        }

        imp.process_badge(badge)  # should not raise

        imp._entry_store.add_entry.assert_not_called()

    def test_run_fetches_and_processes_each_badge(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value="gaben")
        imp.fetch_badges_page = MagicMock(return_value="<html>fake</html>")
        imp.parse_badges = MagicMock(return_value=[{"title": "A"}, {"title": "B"}])
        imp.process_badge = MagicMock()

        imp.run()

        imp.fetch_badges_page.assert_called_once_with("gaben")
        imp.parse_badges.assert_called_once_with(
            "<html>fake</html>",
            fallback_url="https://steamcommunity.com/id/gaben/badges",
        )
        assert imp.process_badge.call_count == 2
