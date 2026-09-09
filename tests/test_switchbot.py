"""Tests for the SwitchBot importer."""

import base64
import hashlib
import hmac
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from lifestream.importers.switchbot import SwitchBotAPI, SwitchbotImporter


class TestSwitchBotAPI:
    def test_init_uses_token_and_secret_from_parameters(self):
        api = SwitchBotAPI(token="tok", secret="sec")
        assert api.token == "tok"
        assert api.secret == "sec"

    def test_init_falls_back_to_config(self):
        with patch("lifestream.importers.switchbot.config") as mock_config:
            mock_config.get.side_effect = lambda section, key: {
                "token": "cfg-tok",
                "secret": "cfg-sec",
            }[key]
            api = SwitchBotAPI()

        assert api.token == "cfg-tok"
        assert api.secret == "cfg-sec"

    def test_signed_headers_sign_matches_hmac_sha256_of_token_t_nonce(self):
        api = SwitchBotAPI(token="tok", secret="sec")

        headers = api._signed_headers()

        expected = (
            base64.b64encode(
                hmac.new(
                    b"sec",
                    f"tok{headers['t']}{headers['nonce']}".encode(),
                    hashlib.sha256,
                ).digest()
            )
            .decode()
            .upper()
        )

        assert headers["sign"] == expected
        assert headers["authorization"] == "tok"
        assert headers["t"].isdigit()

    def test_signed_headers_timestamp_is_current_time_in_milliseconds(self):
        api = SwitchBotAPI(token="tok", secret="sec")
        before = int(datetime.now().timestamp() * 1000)

        headers = api._signed_headers()

        after = int(datetime.now().timestamp() * 1000)
        assert before <= int(headers["t"]) <= after

    def test_call_get_hits_v1_1_endpoint_with_signed_headers(self):
        api = SwitchBotAPI(token="tok", secret="sec")
        response = MagicMock()
        response.json.return_value = {"ok": True}

        with patch(
            "lifestream.importers.switchbot.requests.get", return_value=response
        ) as mock_get:
            result = api.call("get", "devices")

        assert result == {"ok": True}
        mock_get.assert_called_once()
        args, kwargs = mock_get.call_args
        assert args[0] == "https://api.switch-bot.com/v1.1/devices"
        assert kwargs["headers"]["authorization"] == "tok"
        assert "sign" in kwargs["headers"]
        response.raise_for_status.assert_called_once()

    def test_call_post_sets_content_type_and_sends_json_body(self):
        api = SwitchBotAPI(token="tok", secret="sec")
        response = MagicMock()
        response.json.return_value = {"ok": True}

        with patch(
            "lifestream.importers.switchbot.requests.post", return_value=response
        ) as mock_post:
            api.call("post", "devices/1/commands", data={"command": "turnOn"})

        args, kwargs = mock_post.call_args
        assert args[0] == "https://api.switch-bot.com/v1.1/devices/1/commands"
        assert kwargs["json"] == {"command": "turnOn"}
        assert kwargs["headers"]["content-type"] == "application/json; charset=utf8"

    def test_call_unknown_method_raises(self):
        api = SwitchBotAPI(token="tok", secret="sec")
        with pytest.raises(ValueError):
            api.call("delete", "devices")


class TestSwitchbotImporter:
    def _make_importer(self):
        imp = SwitchbotImporter()
        imp._args = imp.parse_args([])
        imp._entry_store = MagicMock()
        return imp

    def test_validate_config_fails_when_keys_missing(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value=None)
        assert imp.validate_config() is False

    def test_validate_config_passes_when_all_keys_present(self):
        imp = self._make_importer()
        imp.get_config = MagicMock(return_value="set")
        assert imp.validate_config() is True

    def test_run_records_temp_and_humidity_for_meter_devices(self):
        imp = self._make_importer()

        mock_api = MagicMock()
        mock_api.call.side_effect = [
            {
                "body": {
                    "deviceList": [
                        {
                            "deviceName": "Living Room",
                            "deviceId": "abc123",
                            "deviceType": "Meter",
                        },
                        {
                            "deviceName": "Front Door",
                            "deviceId": "def456",
                            "deviceType": "Bot",
                        },
                    ]
                }
            },
            {"body": {"temperature": 21.5, "humidity": 47}},
        ]

        with patch(
            "lifestream.importers.switchbot.SwitchBotAPI", return_value=mock_api
        ):
            imp.run()

        mock_api.call.assert_any_call("get", "devices")
        mock_api.call.assert_any_call("get", "devices/abc123/status")
        assert mock_api.call.call_count == 2

        stat_calls = imp._entry_store.add_stat.call_args_list
        assert len(stat_calls) == 2
        assert stat_calls[0].args[1] == "Living Room-temp"
        assert stat_calls[0].args[2] == 21.5
        assert stat_calls[1].args[1] == "Living Room-humid"
        assert stat_calls[1].args[2] == 47
