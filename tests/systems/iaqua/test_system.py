from __future__ import annotations

import urllib.parse
from unittest.mock import MagicMock, patch

import pytest

from iaqualink.const import AQUALINK_API_KEY
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.iaqua.device import IaquaAuxSwitch, IaquaOneTouchSwitch
from iaqualink.systems.iaqua.enums import IaquaSystemType, IaquaTemperatureUnit
from iaqualink.systems.iaqua.system import (
    IAQUA_SESSION_URL,
    IAQUA_COMMAND_SET_ONETOUCH,
    IaquaSystem,
)

from ...base_test_system import TestBaseSystem


class TestIaquaSystem(TestBaseSystem):
    def setUp(self) -> None:
        super().setUp()

        data = {
            "id": 123456,
            "serial_number": "SN123456",
            "created_at": "2017-09-23T01:00:08.000Z",
            "updated_at": "2017-09-23T01:00:08.000Z",
            "name": "Pool",
            "device_type": "iaqua",
            "owner_id": None,
            "updating": False,
            "firmware_version": None,
            "target_firmware_version": None,
            "update_firmware_start_at": None,
            "last_activity_at": None,
        }
        self.sut = AqualinkSystem.from_data(self.client, data=data)
        self.sut_class = IaquaSystem

    async def test_update_success(self) -> None:
        with (
            patch.object(self.sut, "_parse_home_response"),
            patch.object(self.sut, "_parse_devices_response"),
            patch.object(self.sut, "_parse_onetouch_response"),
        ):
            await super().test_update_success()

    async def test_update_offline(self) -> None:
        with (
            patch.object(self.sut, "_parse_home_response") as mock_parse,
            patch.object(self.sut, "_parse_devices_response"),
            patch.object(self.sut, "_parse_onetouch_response"),
        ):
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

    async def test_update_consecutive(self) -> None:
        with (
            patch.object(self.sut, "_parse_home_response"),
            patch.object(self.sut, "_parse_devices_response"),
            patch.object(self.sut, "_parse_onetouch_response"),
        ):
            await super().test_update_consecutive()

    async def test_get_devices_needs_update(self) -> None:
        with (
            patch.object(self.sut, "_parse_home_response"),
            patch.object(self.sut, "_parse_devices_response"),
            patch.object(self.sut, "_parse_onetouch_response"),
        ):
            await super().test_get_devices_needs_update()

    async def test_parse_devices_offline(self) -> None:
        message = {
            "message": "",
            "devices_screen": [{"status": "Offline"}],
        }
        response = MagicMock()
        response.json.return_value = message

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
        response.json.return_value = message

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

    async def test_parse_home_sets_system_type_and_temp_unit(self) -> None:
        message = {
            "message": "",
            "home_screen": [
                {"status": "Online"},
                {"response": ""},
                {"system_type": "1"},
                {"temp_scale": "F"},
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        self.sut._parse_home_response(response)
        assert self.sut.system_type is IaquaSystemType.POOL_ONLY
        assert self.sut.temp_unit is IaquaTemperatureUnit.FAHRENHEIT

    async def test_parse_home_sets_celsius_temp_unit(self) -> None:
        message = {
            "message": "",
            "home_screen": [
                {"status": "Online"},
                {"response": ""},
                {"system_type": "0"},
                {"temp_scale": "C"},
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        self.sut._parse_home_response(response)
        assert self.sut.system_type is IaquaSystemType.SPA_AND_POOL
        assert self.sut.temp_unit is IaquaTemperatureUnit.CELSIUS

    async def test_parse_home_sets_dual_system_type(self) -> None:
        message = {
            "message": "",
            "home_screen": [
                {"status": "Online"},
                {"response": ""},
                {"system_type": "2"},
                {"temp_scale": "F"},
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        self.sut._parse_home_response(response)
        assert self.sut.system_type is IaquaSystemType.DUAL

    async def test_parse_home_ignores_unknown_system_type(self) -> None:
        message = {
            "message": "",
            "home_screen": [
                {"status": "Online"},
                {"response": ""},
                {"system_type": "99"},
                {"temp_scale": "F"},
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        self.sut._parse_home_response(response)
        assert self.sut.system_type is None

    async def test_parse_home_ignores_unknown_temp_scale(self) -> None:
        message = {
            "message": "",
            "home_screen": [
                {"status": "Online"},
                {"response": ""},
                {"system_type": "1"},
                {"temp_scale": "K"},
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        self.sut._parse_home_response(response)
        assert self.sut.temp_unit is None

    async def test_parse_home_offline_when_service(self) -> None:
        message = {
            "message": "",
            "home_screen": [
                {"status": "Service"},
                {"response": ""},
                {"system_type": ""},
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        with pytest.raises(AqualinkSystemOfflineException):
            self.sut._parse_home_response(response)

    async def test_parse_devices_offline_when_service(self) -> None:
        message = {"message": "", "devices_screen": [{"status": "Service"}]}
        response = MagicMock()
        response.json.return_value = message

        with pytest.raises(AqualinkSystemOfflineException):
            self.sut._parse_devices_response(response)

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

    async def test_parse_onetouch_offline(self) -> None:
        message = {"message": "", "onetouch_screen": [{"status": "Offline"}]}
        response = MagicMock()
        response.json.return_value = message

        with pytest.raises(AqualinkSystemOfflineException):
            self.sut._parse_onetouch_response(response)
        assert self.sut.devices == {}

    async def test_parse_onetouch_good(self) -> None:
        message = {
            "message": "",
            "onetouch_screen": [
                {"status": "Online"},
                {"response": ""},
                {
                    "onetouch_1": [
                        {"state": "0"},
                        {"label": "Morning Scene"},
                        {"status": "1"},
                    ]
                },
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        expected = {
            "onetouch_1": IaquaOneTouchSwitch(
                system=self.sut,
                data={
                    "name": "onetouch_1",
                    "state": "0",
                    "label": "Morning Scene",
                    "status": "1",
                },
            )
        }
        self.sut._parse_onetouch_response(response)
        assert self.sut.devices == expected

    @patch("httpx.AsyncClient.request")
    async def test_onetouch_request(self, mock_request) -> None:
        mock_request.return_value.status_code = 200

        await self.sut._send_onetouch_screen_request()

    @patch("httpx.AsyncClient.request")
    async def test_onetouch_request_unauthorized(self, mock_request) -> None:
        mock_request.return_value.status_code = 401

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await self.sut._send_onetouch_screen_request()

    @patch("httpx.AsyncClient.request")
    async def test_set_onetouch(self, mock_request) -> None:
        mock_request.return_value.status_code = 200
        with patch.object(self.sut, "_parse_onetouch_response") as mock_parse:
            await self.sut.set_onetouch("onetouch_1")

            called_url = mock_request.call_args[0][1]
            assert f"{IAQUA_COMMAND_SET_ONETOUCH}_1" in called_url
            mock_parse.assert_called_once_with(mock_request.return_value)

    async def test_update_onetouch_failure_is_nonfatal(self) -> None:
        """A failing onetouch request must not raise; update() should succeed."""
        with (
            patch.object(self.sut, "_send_home_screen_request"),
            patch.object(self.sut, "_send_devices_screen_request"),
            patch.object(
                self.sut,
                "_send_onetouch_screen_request",
                side_effect=AqualinkServiceException,
            ),
            patch.object(self.sut, "_parse_home_response"),
            patch.object(self.sut, "_parse_devices_response"),
        ):
            # Should not raise despite onetouch failure.
            await self.sut.update()

        assert self.sut._onetouch_supported is False

    async def test_update_onetouch_throttle_does_not_disable(self) -> None:
        """A 429 on onetouch must propagate and not permanently disable it."""
        with (
            patch.object(self.sut, "_send_home_screen_request"),
            patch.object(self.sut, "_send_devices_screen_request"),
            patch.object(
                self.sut,
                "_send_onetouch_screen_request",
                side_effect=AqualinkServiceThrottledException,
            ),
            patch.object(self.sut, "_parse_home_response"),
            patch.object(self.sut, "_parse_devices_response"),
        ):
            with pytest.raises(AqualinkServiceThrottledException):
                await self.sut.update()

        assert self.sut._onetouch_supported is None

    async def test_update_onetouch_disabled_after_first_failure(self) -> None:
        """After a onetouch failure, subsequent updates skip the request."""
        with (
            patch.object(self.sut, "_send_home_screen_request"),
            patch.object(self.sut, "_send_devices_screen_request"),
            patch.object(
                self.sut,
                "_send_onetouch_screen_request",
                side_effect=AqualinkServiceException,
            ) as onetouch_mock,
            patch.object(self.sut, "_parse_home_response"),
            patch.object(self.sut, "_parse_devices_response"),
        ):
            await self.sut.update()
            assert onetouch_mock.call_count == 1

            # Reset timer so a second update() is not rate-limited.
            self.sut.last_refresh = 0
            onetouch_mock.reset_mock()
            await self.sut.update()
            assert onetouch_mock.call_count == 0

    async def test_update_onetouch_disabled_by_home_flag(self) -> None:
        """oneTouch=0 in home response disables onetouch polling immediately."""
        message = {
            "home_screen": [
                {"status": "Online"},
                {"response": ""},
                {"response": ""},
                {"temp_scale": "F"},
                {"one_touch": "0"},
            ]
        }
        response = MagicMock()
        response.json.return_value = message

        with (
            patch.object(
                self.sut, "_send_home_screen_request", return_value=response
            ),
            patch.object(
                self.sut, "_send_devices_screen_request", return_value=response
            ),
            patch.object(
                self.sut, "_send_onetouch_screen_request"
            ) as onetouch_req,
            patch.object(self.sut, "_parse_devices_response"),
            patch.object(self.sut, "_parse_onetouch_response"),
        ):
            await self.sut.update()
            # Home response is parsed first; one_touch=0 disables the request
            # before it is ever issued — not just on the second poll.
            assert onetouch_req.call_count == 0

        assert self.sut._onetouch_supported is False

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
