from __future__ import annotations

import json
import urllib.parse
from unittest.mock import MagicMock, patch

import pytest

from iaqualink.const import AQUALINK_API_KEY
from iaqualink.exception import (
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.iaqua.device import IaquaAuxSwitch
from iaqualink.systems.iaqua.system import IAQUA_SESSION_URL, IaquaSystem
from iaqualink.types import DevicesResponseElement

from ...base_test_system import TestBaseSystem


class TestIaquaSystem(TestBaseSystem):
    def setUp(self) -> None:
        super().setUp()

        data = DevicesResponseElement(
            id=123456,
            serial_number="SN123456",
            name="Pool",
            device_type="iaqua",
        )
        self.sut = AqualinkSystem.from_data(self.client, data=data)
        self.sut_class = IaquaSystem

    async def test_update_success(self) -> None:
        with (
            patch.object(self.sut, "_parse_home_response"),
            patch.object(self.sut, "_parse_devices_response"),
        ):
            await super().test_update_success()

    async def test_update_offline(self) -> None:
        with patch.object(self.sut, "_parse_home_response") as mock_parse:
            mock_parse.side_effect = AqualinkSystemOfflineException
            with pytest.raises(AqualinkSystemOfflineException):
                await super().test_update_success()
            assert self.sut.status is SystemStatus.OFFLINE

    async def test_update_throttled(self) -> None:
        with patch.object(self.sut, "_send_home_screen_request") as mock_req:
            mock_req.side_effect = AqualinkServiceThrottledException
            with pytest.raises(AqualinkServiceThrottledException):
                await self.sut.update()
        assert self.sut.status is SystemStatus.UNKNOWN

    async def test_get_devices_needs_update(self) -> None:
        with (
            patch.object(self.sut, "_parse_home_response"),
            patch.object(self.sut, "_parse_devices_response"),
        ):
            await super().test_get_devices_needs_update()

    async def test_parse_home_offline(self) -> None:
        message = {
            "message": "",
            "serial": "",
            "home_screen": [{"status": "Offline"}],
        }
        response = MagicMock()
        response.text = json.dumps(message)

        with pytest.raises(AqualinkSystemOfflineException):
            self.sut._parse_home_response(response)
        assert self.sut.devices == {}

    async def test_parse_home_good(self) -> None:
        message = {
            "message": "",
            "serial": "",
            "home_screen": [
                {"status": "Online"},
                {"response": ""},
                {"system_type": "IQPRO+"},
                {"temp_scale": "F"},
                {"spa_temp": "90"},
                {"pool_temp": "85"},
            ],
        }
        response = MagicMock()
        response.text = json.dumps(message)

        self.sut._parse_home_response(response)
        assert "spa_temp" in self.sut.devices
        assert "pool_temp" in self.sut.devices
        assert self.sut.temp_unit == "F"

    async def test_parse_devices_offline(self) -> None:
        message = {"message": "", "devices_screen": [{"status": "Offline"}]}
        response = MagicMock()
        response.text = json.dumps(message)

        with pytest.raises(AqualinkSystemOfflineException):
            self.sut._parse_devices_response(response)
        assert self.sut.devices == {}

    async def test_parse_devices_good(self) -> None:
        message = {
            "message": "",
            "devices_screen": [
                {"status": "Online"},
                {"response": ""},
                {"group": "1"},
                {
                    "aux_B1": [
                        {"state": "0"},
                        {"label": "Label B1"},
                        {"icon": "aux_1_0.png"},
                        {"type": "0"},
                        {"subtype": "0"},
                    ]
                },
            ],
        }
        response = MagicMock()
        response.text = json.dumps(message)

        expected = {
            "aux_B1": IaquaAuxSwitch(
                system=self.sut,
                data={
                    "aux": "B1",
                    "name": "aux_B1",
                    "state": "0",
                    "label": "Label B1",
                    "icon": "aux_1_0.png",
                    "type": "0",
                    "subtype": "0",
                },
            )
        }
        self.sut._parse_devices_response(response)
        assert self.sut.devices == expected

    async def test_parse_devices_skipped_on_nan_state(self) -> None:
        existing = MagicMock()
        self.sut.devices["aux_existing"] = existing

        message = {
            "message": "",
            "devices_screen": [
                {"status": "Online"},
                {"response": ""},
                {"group": "1"},
                {
                    "aux_1": [
                        {"state": "NaN"},
                        {"label": "AUX 1"},
                        {"icon": "aux_NaN_NaN.png"},
                        {"type": "NaN"},
                        {"subtype": "NaN"},
                    ]
                },
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        self.sut._parse_devices_response(response)
        assert self.sut.devices == {"aux_existing": existing}

    async def test_parse_home_skipped_on_empty_system_type(self) -> None:
        existing = MagicMock()
        self.sut.devices["pool_pump"] = existing

        message = {
            "message": "",
            "home_screen": [
                {"status": "Online"},
                {"response": ""},
                {"system_type": ""},
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        self.sut._parse_home_response(response)
        assert self.sut.devices == {"pool_pump": existing}

    @patch("httpx.AsyncClient.request")
    async def test_home_request(self, mock_request) -> None:
        mock_request.return_value.status_code = 200

        await self.sut._send_home_screen_request()

    @patch("httpx.AsyncClient.request")
    async def test_home_request_unauthorized(self, mock_request) -> None:
        mock_request.return_value.status_code = 401

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await self.sut._send_home_screen_request()

    @patch("httpx.AsyncClient.request")
    async def test_devices_request(self, mock_request) -> None:
        mock_request.return_value.status_code = 200

        await self.sut._send_devices_screen_request()

    @patch("httpx.AsyncClient.request")
    async def test_devices_request_unauthorized(self, mock_request) -> None:
        mock_request.return_value.status_code = 401

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await self.sut._send_devices_screen_request()

    @patch("httpx.AsyncClient.request")
    async def test_session_request_retries_after_refresh(
        self, mock_request
    ) -> None:
        mock_request.side_effect = [
            MagicMock(status_code=401),
            MagicMock(status_code=200),
        ]
        self.client.client_id = "old-session-id"
        self.client.id_token = "old-id-token"

        async def fake_refresh() -> None:
            self.client.client_id = "new-session-id"
            self.client.id_token = "new-id-token"

        with patch.object(
            self.client, "_refresh_auth", side_effect=fake_refresh
        ) as mock_refresh:
            await self.sut._send_home_screen_request()

        retry_url = mock_request.call_args_list[1][0][1]
        retry_headers = mock_request.call_args_list[1][1]["headers"]
        retry_params = urllib.parse.parse_qs(
            urllib.parse.urlparse(retry_url).query
        )

        mock_refresh.assert_awaited_once()
        assert retry_params["sessionID"] == ["new-session-id"]
        assert retry_headers["Authorization"] == "Bearer new-id-token"

    @patch("httpx.AsyncClient.request")
    async def test_session_request_refreshes_only_once_on_repeated_401(
        self, mock_request
    ) -> None:
        mock_request.side_effect = [
            MagicMock(status_code=401),
            MagicMock(status_code=401),
        ]

        with (
            patch.object(
                self.client, "_refresh_auth", return_value=None
            ) as mock_refresh,
            pytest.raises(AqualinkServiceUnauthorizedException),
        ):
            await self.sut._send_home_screen_request()

        mock_refresh.assert_awaited_once()

    @patch("httpx.AsyncClient.request")
    async def test_session_request_uses_v2_url(self, mock_request) -> None:
        mock_request.return_value.status_code = 200

        await self.sut._send_home_screen_request()

        called_url = mock_request.call_args[0][1]
        assert called_url.startswith(IAQUA_SESSION_URL)

    @patch("httpx.AsyncClient.request")
    async def test_session_request_sends_auth_headers(
        self, mock_request
    ) -> None:
        mock_request.return_value.status_code = 200
        self.client.id_token = "test-id-token"

        await self.sut._send_home_screen_request()

        headers = mock_request.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer test-id-token"
        assert headers["api_key"] == AQUALINK_API_KEY
