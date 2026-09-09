"""Tests for the Last.fm importer."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from lifestream.importers.base import ConfigurationError
from lifestream.importers.lastfm import LastfmImporter


def _track(
    artist="Artist",
    name="Track",
    uts="1700000000",
    url="https://www.last.fm/music/Artist/_/Track",
    images=None,
    now_playing=False,
):
    track = {
        "artist": {"#text": artist, "mbid": ""},
        "name": name,
        "url": url,
        "image": (
            images
            if images is not None
            else [
                {"size": "small", "#text": "https://img/small.png"},
                {"size": "medium", "#text": "https://img/medium.png"},
                {"size": "large", "#text": "https://img/large.png"},
                {"size": "extralarge", "#text": "https://img/extralarge.png"},
            ]
        ),
    }
    if now_playing:
        track["@attr"] = {"nowplaying": "true"}
    else:
        track["date"] = {"uts": uts, "#text": "some date"}
    return track


def _response(payload, status_ok=True):
    response = MagicMock()
    response.json.return_value = payload
    if not status_ok:
        response.raise_for_status.side_effect = Exception("HTTP error")
    return response


class TestLastfmImporter:
    def _make_importer(self, args=None):
        imp = LastfmImporter()
        imp._args = imp.parse_args(args or [])
        imp._entry_store = MagicMock()
        imp.get_config = MagicMock(
            side_effect=lambda k, fallback=None: {
                "username": "testuser",
                "api_key": "testkey",
            }.get(k, fallback)
        )
        return imp

    def test_validate_config_fails_when_keys_missing(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value=None)
        assert imp.validate_config() is False

    def test_validate_config_passes_when_all_keys_present(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value="set")
        assert imp.validate_config() is True

    def test_run_calls_official_api_with_expected_params(self):
        imp = self._make_importer(["--limit", "25"])
        payload = {"recenttracks": {"track": []}}

        with patch(
            "lifestream.importers.lastfm.requests.get",
            return_value=_response(payload),
        ) as mock_get:
            imp.run()

        args, kwargs = mock_get.call_args
        assert args[0] == "https://ws.audioscrobbler.com/2.0/"
        assert kwargs["params"] == {
            "method": "user.getrecenttracks",
            "user": "testuser",
            "api_key": "testkey",
            "format": "json",
            "limit": 25,
        }

    def test_run_adds_an_entry_per_scrobbled_track(self):
        imp = self._make_importer()
        payload = {
            "recenttracks": {
                "track": [
                    _track(artist="Boards of Canada", name="Roygbiv", uts="1700000000")
                ]
            }
        }

        with patch(
            "lifestream.importers.lastfm.requests.get",
            return_value=_response(payload),
        ):
            imp.run()

        imp._entry_store.add_entry.assert_called_once()
        args, kwargs = imp._entry_store.add_entry.call_args
        assert args[0] == "lastfm"
        assert args[2] == "Boards of Canada – Roygbiv"
        assert args[3] == "lastfm"
        assert args[4] == datetime.fromtimestamp(1700000000, tz=timezone.utc)
        assert kwargs["url"] == "https://www.last.fm/music/Artist/_/Track"
        assert kwargs["image"] == "https://img/extralarge.png"
        assert kwargs["fulldata_json"]["name"] == "Roygbiv"

    def test_run_skips_now_playing_track(self):
        imp = self._make_importer()
        payload = {
            "recenttracks": {
                "track": [
                    _track(name="Currently Playing", now_playing=True),
                    _track(name="Already Scrobbled"),
                ]
            }
        }

        with patch(
            "lifestream.importers.lastfm.requests.get",
            return_value=_response(payload),
        ):
            imp.run()

        imp._entry_store.add_entry.assert_called_once()
        assert imp._entry_store.add_entry.call_args.args[2].endswith(
            "Already Scrobbled"
        )

    def test_run_normalizes_single_track_dict_response(self):
        """Last.fm returns a bare dict, not a one-item list, for a single result."""
        imp = self._make_importer()
        payload = {"recenttracks": {"track": _track(name="Solo Track")}}

        with patch(
            "lifestream.importers.lastfm.requests.get",
            return_value=_response(payload),
        ):
            imp.run()

        imp._entry_store.add_entry.assert_called_once()

    def test_run_raises_configuration_error_on_api_error_response(self):
        imp = self._make_importer()
        payload = {"error": 10, "message": "Invalid API Key"}

        with patch(
            "lifestream.importers.lastfm.requests.get",
            return_value=_response(payload),
        ):
            with pytest.raises(ConfigurationError, match="Invalid API Key"):
                imp.run()

        imp._entry_store.add_entry.assert_not_called()

    def test_track_image_falls_back_through_sizes(self):
        track = _track(images=[{"size": "small", "#text": "https://img/small.png"}])
        assert LastfmImporter._track_image(track) == "https://img/small.png"

    def test_track_image_empty_when_no_images(self):
        track = _track(images=[])
        assert LastfmImporter._track_image(track) == ""

    def test_track_id_is_stable_for_same_track_and_differs_by_timestamp(self):
        track1 = _track(uts="1700000000")
        track2 = _track(uts="1700000000")
        track3 = _track(uts="1700000999")

        assert LastfmImporter._track_id(track1) == LastfmImporter._track_id(track2)
        assert LastfmImporter._track_id(track1) != LastfmImporter._track_id(track3)
