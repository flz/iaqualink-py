from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any, cast
from unittest.mock import MagicMock, patch

import pytest
import respx.router

from iaqualink.client import AqualinkClient
from iaqualink.const import AQUALINK_API_KEY
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
)
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.iaqua.device import (
    IaquaClimate,
    IaquaHeatPump,
    IaquaHeatPumpAlertSensor,
    IaquaHeatPumpMode,
    IaquaOneTouchSwitch,
    IaquaSetPoint,
    IaquaVSPump,
)
from iaqualink.systems.iaqua.enums import IaquaSystemType, IaquaTemperatureUnit
from iaqualink.systems.iaqua.system import (
    IAQUA_COMMAND_ENABLE_DISABLE_HPM,
    IAQUA_COMMAND_GET_MASTER_DEVICE_LIST,
    IAQUA_COMMAND_GET_VSP_APPMODELSERIALS,
    IAQUA_COMMAND_GET_VSP_NAMES,
    IAQUA_COMMAND_GET_VSP_SPEED,
    IAQUA_COMMAND_SET_ONETOUCH,
    IAQUA_COMMAND_SET_VSP_SPEED,
    IAQUA_COMMAND_SETPOINT_HPM_TEMP,
    IAQUA_COMMAND_SWITCH_HPM_MODE,
    IAQUA_SESSION_URL,
    IAQUA_SESSION_V1_URL,
    IaquaSystem,
)

from ...conftest import dotstar, resp_200

_SYSTEM_DATA: dict[str, Any] = {
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


def _make_iaqua_system() -> tuple[AqualinkClient, IaquaSystem]:
    client = AqualinkClient("foo", "bar")
    sut = cast(
        IaquaSystem, AqualinkSystem.from_data(client, data={**_SYSTEM_DATA})
    )
    return client, sut


def _set_online_for(sut: AqualinkSystem) -> Callable[[object], None]:
    def _inner(_response: object) -> None:
        sut.status = SystemStatus.ONLINE

    return _inner


def _home_response(extra: list[dict]) -> MagicMock:
    message = {
        "home_screen": [
            {"status": "Online"},
            {"response": ""},
            {"system_type": "1"},
            {"temp_scale": "F"},
            *extra,
        ],
    }
    r = MagicMock()
    r.json.return_value = message
    return r


def _vsp_mock_response(mock_request: MagicMock) -> None:
    resp = MagicMock()
    resp.status_code = 200
    resp.reason_phrase = "OK"
    resp.json.return_value = {}
    mock_request.return_value = resp


class TestIaquaSystem:
    async def test_refresh_success(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        _, sut = _make_iaqua_system()
        respx_mock.route(dotstar).mock(resp_200)
        with (
            patch.object(
                sut, "_parse_home_response", side_effect=_set_online_for(sut)
            ),
            patch.object(sut, "_parse_devices_response"),
            patch.object(sut, "_parse_onetouch_response"),
        ):
            await sut.refresh()
        assert len(respx_mock.calls) > 0
        assert sut.status is SystemStatus.ONLINE

    async def test_refresh_offline(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        _, sut = _make_iaqua_system()

        def _set_offline(_response: object) -> None:
            sut.status = SystemStatus.OFFLINE

        respx_mock.route(dotstar).mock(resp_200)
        with (
            patch.object(sut, "_parse_home_response", side_effect=_set_offline),
            patch.object(sut, "_parse_devices_response"),
            patch.object(sut, "_parse_onetouch_response"),
        ):
            await sut.refresh()
        assert sut.status is SystemStatus.OFFLINE

    async def test_parse_devices_offline(self) -> None:
        _, sut = _make_iaqua_system()
        message = {
            "message": "",
            "devices_screen": [{"status": "Offline"}],
        }
        response = MagicMock()
        response.json.return_value = message

        sut._parse_devices_response(response)
        assert sut.devices == {}

    async def test_parse_devices_skipped_on_nan_state(self) -> None:
        _, sut = _make_iaqua_system()
        existing = MagicMock()
        sut.devices["aux_existing"] = existing

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

        sut._parse_devices_response(response)
        assert sut.devices == {"aux_existing": existing}

    async def test_parse_home_sets_system_type_and_temp_unit(self) -> None:
        _, sut = _make_iaqua_system()
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

        sut._parse_home_response(response)
        assert sut.system_type is IaquaSystemType.POOL_ONLY
        assert sut.temp_unit is IaquaTemperatureUnit.FAHRENHEIT

    async def test_parse_home_sets_celsius_temp_unit(self) -> None:
        _, sut = _make_iaqua_system()
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

        sut._parse_home_response(response)
        assert sut.system_type is IaquaSystemType.SPA_AND_POOL
        assert sut.temp_unit is IaquaTemperatureUnit.CELSIUS

    async def test_parse_home_sets_dual_system_type(self) -> None:
        _, sut = _make_iaqua_system()
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

        sut._parse_home_response(response)
        assert sut.system_type is IaquaSystemType.DUAL

    async def test_parse_home_ignores_unknown_system_type(self) -> None:
        _, sut = _make_iaqua_system()
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

        sut._parse_home_response(response)
        assert sut.system_type is None

    async def test_parse_home_ignores_unknown_temp_scale(self) -> None:
        _, sut = _make_iaqua_system()
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

        sut._parse_home_response(response)
        assert sut.temp_unit is None

    async def test_parse_home_offline(self) -> None:
        _, sut = _make_iaqua_system()
        message = {
            "message": "",
            "home_screen": [
                {"status": "Offline"},
                {"response": ""},
                {"system_type": ""},
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        sut._parse_home_response(response)
        assert sut.status is SystemStatus.OFFLINE

    async def test_parse_home_offline_when_service(self) -> None:
        _, sut = _make_iaqua_system()
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

        sut._parse_home_response(response)
        assert sut.status is SystemStatus.SERVICE

    async def test_parse_home_unknown_status(self) -> None:
        _, sut = _make_iaqua_system()
        message = {
            "message": "",
            "home_screen": [
                {"status": "Unknown"},
                {"response": ""},
                {"system_type": ""},
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        sut._parse_home_response(response)
        assert sut.status is SystemStatus.UNKNOWN

    async def test_parse_home_empty_status(self) -> None:
        _, sut = _make_iaqua_system()
        message = {
            "message": "",
            "home_screen": [
                {"status": ""},
                {"response": ""},
                {"system_type": ""},
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        sut._parse_home_response(response)
        assert sut.status is SystemStatus.UNKNOWN

    async def test_parse_home_missing_status(self) -> None:
        _, sut = _make_iaqua_system()
        message = {
            "message": "",
            "home_screen": [{"response": ""}, {"system_type": ""}],
        }
        response = MagicMock()
        response.json.return_value = message

        sut._parse_home_response(response)
        assert sut.status is SystemStatus.UNKNOWN

    async def test_parse_home_unrecognised_status(self) -> None:
        _, sut = _make_iaqua_system()
        message = {
            "message": "",
            "home_screen": [
                {"status": "Updating"},
                {"response": ""},
                {"system_type": ""},
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        sut._parse_home_response(response)
        assert sut.status is SystemStatus.UNKNOWN

    async def test_parse_home_online(self) -> None:
        _, sut = _make_iaqua_system()
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

        sut._parse_home_response(response)
        assert sut.status is SystemStatus.ONLINE

    async def test_parse_devices_skipped_when_service(self) -> None:
        _, sut = _make_iaqua_system()
        message = {"message": "", "devices_screen": [{"status": "Service"}]}
        response = MagicMock()
        response.json.return_value = message

        sut._parse_devices_response(response)
        assert sut.devices == {}

    async def test_parse_home_skipped_on_empty_system_type(self) -> None:
        _, sut = _make_iaqua_system()
        existing = MagicMock()
        sut.devices["pool_pump"] = existing

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

        sut._parse_home_response(response)
        assert sut.devices == {"pool_pump": existing}

    async def test_parse_home_sets_onetouch_supported_true(self) -> None:
        _, sut = _make_iaqua_system()
        message = {
            "onetouch": "true",
            "home_screen": [
                {"status": "Online"},
                {"response": ""},
                {"system_type": "iaqua"},
                {"temp_scale": "F"},
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        sut._parse_home_response(response)
        assert sut._onetouch_supported is True

    async def test_parse_home_sets_onetouch_supported_false_when_absent(
        self,
    ) -> None:
        _, sut = _make_iaqua_system()
        message = {
            "home_screen": [
                {"status": "Online"},
                {"response": ""},
                {"system_type": "iaqua"},
                {"temp_scale": "F"},
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        sut._parse_home_response(response)
        assert sut._onetouch_supported is False

    @patch("httpx.AsyncClient.request")
    async def test_home_request(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        mock_request.return_value.status_code = 200

        await sut._send_home_screen_request()

    @patch("httpx.AsyncClient.request")
    async def test_home_request_unauthorized(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        mock_request.return_value.status_code = 401

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await sut._send_home_screen_request()

    @patch("httpx.AsyncClient.request")
    async def test_devices_request(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        mock_request.return_value.status_code = 200

        await sut._send_devices_screen_request()

    @patch("httpx.AsyncClient.request")
    async def test_devices_request_unauthorized(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        mock_request.return_value.status_code = 401

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await sut._send_devices_screen_request()

    async def test_parse_onetouch_skipped_when_offline(self) -> None:
        _, sut = _make_iaqua_system()
        message = {"message": "", "onetouch_screen": [{"status": "Offline"}]}
        response = MagicMock()
        response.json.return_value = message

        sut._parse_onetouch_response(response)
        assert sut.devices == {}

    async def test_parse_onetouch_skipped_when_service(self) -> None:
        _, sut = _make_iaqua_system()
        message = {"message": "", "onetouch_screen": [{"status": "Service"}]}
        response = MagicMock()
        response.json.return_value = message

        sut._parse_onetouch_response(response)
        assert sut.devices == {}

    async def test_parse_onetouch_skips_disabled_device(self) -> None:
        _, sut = _make_iaqua_system()
        message = {
            "message": "",
            "onetouch_screen": [
                {"status": "Online"},
                {"response": ""},
                {
                    "onetouch_1": [
                        {"state": "0"},
                        {"label": "Morning Scene"},
                        {"status": "0"},
                    ]
                },
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        sut._parse_onetouch_response(response)
        assert "onetouch_1" not in sut.devices

    async def test_parse_onetouch_removes_previously_added_disabled_device(
        self,
    ) -> None:
        _, sut = _make_iaqua_system()
        existing = IaquaOneTouchSwitch(
            system=sut,
            data={"name": "onetouch_1", "state": "1", "status": "1"},
        )
        sut.devices["onetouch_1"] = existing

        message = {
            "message": "",
            "onetouch_screen": [
                {"status": "Online"},
                {"response": ""},
                {
                    "onetouch_1": [
                        {"state": "0"},
                        {"label": "Morning Scene"},
                        {"status": "0"},
                    ]
                },
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        sut._parse_onetouch_response(response)
        assert "onetouch_1" not in sut.devices

    @patch("httpx.AsyncClient.request")
    async def test_onetouch_request(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        mock_request.return_value.status_code = 200

        await sut._send_onetouch_screen_request()

    @patch("httpx.AsyncClient.request")
    async def test_onetouch_request_unauthorized(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        mock_request.return_value.status_code = 401

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await sut._send_onetouch_screen_request()

    @patch("httpx.AsyncClient.request")
    async def test_set_onetouch(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        mock_request.return_value.status_code = 200
        with patch.object(sut, "_parse_onetouch_response") as mock_parse:
            await sut.set_onetouch("onetouch_1")

            called_params = mock_request.call_args[1]["params"]
            assert called_params["command"] == f"{IAQUA_COMMAND_SET_ONETOUCH}_1"
            mock_parse.assert_called_once_with(mock_request.return_value)

    async def test_refresh_onetouch_failure_raises(self) -> None:
        """A failing onetouch request raises and sets status to DISCONNECTED."""
        _, sut = _make_iaqua_system()
        sut._onetouch_supported = True

        with (
            patch.object(sut, "_send_home_screen_request"),
            patch.object(sut, "_send_devices_screen_request"),
            patch.object(
                sut,
                "_send_onetouch_screen_request",
                side_effect=AqualinkServiceException,
            ),
            patch.object(
                sut, "_parse_home_response", side_effect=_set_online_for(sut)
            ),
            patch.object(sut, "_parse_devices_response"),
        ):
            with pytest.raises(AqualinkServiceException):
                await sut.refresh()

        assert sut.status is SystemStatus.DISCONNECTED
        assert sut._onetouch_supported is True

    async def test_refresh_onetouch_throttle_raises(self) -> None:
        """A 429 on onetouch propagates and does not disable onetouch."""
        _, sut = _make_iaqua_system()
        sut._onetouch_supported = True

        with (
            patch.object(sut, "_send_home_screen_request"),
            patch.object(sut, "_send_devices_screen_request"),
            patch.object(
                sut,
                "_send_onetouch_screen_request",
                side_effect=AqualinkServiceThrottledException,
            ),
            patch.object(
                sut, "_parse_home_response", side_effect=_set_online_for(sut)
            ),
            patch.object(sut, "_parse_devices_response"),
        ):
            with pytest.raises(AqualinkServiceThrottledException):
                await sut.refresh()

        assert sut.status is SystemStatus.UNKNOWN
        assert sut._onetouch_supported is True

    async def test_refresh_onetouch_not_requested_when_unsupported(
        self,
    ) -> None:
        """When home response reports no onetouch, the request is never issued."""
        _, sut = _make_iaqua_system()

        with (
            patch.object(sut, "_send_home_screen_request"),
            patch.object(sut, "_send_devices_screen_request"),
            patch.object(sut, "_send_onetouch_screen_request") as onetouch_req,
            patch.object(
                sut, "_parse_home_response", side_effect=_set_online_for(sut)
            ),
            patch.object(sut, "_parse_devices_response"),
        ):
            # _onetouch_supported starts None (falsy) — request must be skipped.
            await sut.refresh()
            assert onetouch_req.call_count == 0

    async def test_refresh_onetouch_enabled_by_home_flag(self) -> None:
        """onetouch='true' in home response enables onetouch polling."""
        _, sut = _make_iaqua_system()
        message = {
            "onetouch": "true",
            "home_screen": [
                {"status": "Online"},
                {"response": ""},
                {"system_type": "iaqua"},
                {"temp_scale": "F"},
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        with (
            patch.object(
                sut, "_send_home_screen_request", return_value=response
            ),
            patch.object(
                sut, "_send_devices_screen_request", return_value=response
            ),
            patch.object(
                sut, "_send_onetouch_screen_request", return_value=response
            ) as onetouch_req,
            patch.object(sut, "_parse_devices_response"),
            patch.object(sut, "_parse_onetouch_response"),
        ):
            await sut.refresh()
            assert onetouch_req.call_count == 1

        assert sut._onetouch_supported is True

    async def test_refresh_full_forces_onetouch_when_unsupported(self) -> None:
        """full=True forces get_onetouch even when onetouch is not supported."""
        _, sut = _make_iaqua_system()

        with (
            patch.object(sut, "_send_home_screen_request"),
            patch.object(sut, "_send_devices_screen_request"),
            patch.object(sut, "_send_onetouch_screen_request") as onetouch_req,
            patch.object(
                sut, "_parse_home_response", side_effect=_set_online_for(sut)
            ),
            patch.object(sut, "_parse_devices_response"),
            patch.object(sut, "_parse_onetouch_response"),
        ):
            # _onetouch_supported starts None (falsy) — would normally be skipped.
            await sut.refresh(full=True)
            assert onetouch_req.call_count == 1

    async def test_refresh_full_forces_devices_and_onetouch_when_offline(
        self,
    ) -> None:
        """full=True forces get_devices/get_onetouch even when status is not ONLINE."""
        _, sut = _make_iaqua_system()

        def _set_offline(_response: object) -> None:
            sut.status = SystemStatus.OFFLINE

        with (
            patch.object(sut, "_send_home_screen_request"),
            patch.object(sut, "_send_devices_screen_request") as devices_req,
            patch.object(sut, "_send_onetouch_screen_request") as onetouch_req,
            patch.object(sut, "_parse_home_response", side_effect=_set_offline),
            patch.object(sut, "_parse_devices_response"),
            patch.object(sut, "_parse_onetouch_response"),
        ):
            await sut.refresh(full=True)
            assert devices_req.call_count == 1
            assert onetouch_req.call_count == 1

    async def test_refresh_not_full_skips_devices_and_onetouch_when_offline(
        self,
    ) -> None:
        """full=False (default) skips get_devices/get_onetouch when status is not ONLINE."""
        _, sut = _make_iaqua_system()

        def _set_offline(_response: object) -> None:
            sut.status = SystemStatus.OFFLINE

        with (
            patch.object(sut, "_send_home_screen_request"),
            patch.object(sut, "_send_devices_screen_request") as devices_req,
            patch.object(sut, "_send_onetouch_screen_request") as onetouch_req,
            patch.object(sut, "_parse_home_response", side_effect=_set_offline),
        ):
            await sut.refresh()
            assert devices_req.call_count == 0
            assert onetouch_req.call_count == 0

    async def test_refresh_onetouch_disabled_by_home_flag(self) -> None:
        """Absent or false onetouch flag in home response skips the request."""
        _, sut = _make_iaqua_system()
        message = {
            "home_screen": [
                {"status": "Online"},
                {"response": ""},
                {"system_type": "iaqua"},
                {"temp_scale": "F"},
            ],
        }
        response = MagicMock()
        response.json.return_value = message

        with (
            patch.object(
                sut, "_send_home_screen_request", return_value=response
            ),
            patch.object(
                sut, "_send_devices_screen_request", return_value=response
            ),
            patch.object(sut, "_send_onetouch_screen_request") as onetouch_req,
            patch.object(sut, "_parse_devices_response"),
            patch.object(sut, "_parse_onetouch_response"),
        ):
            await sut.refresh()
            assert onetouch_req.call_count == 0

        assert sut._onetouch_supported is False

    @patch("httpx.AsyncClient.request")
    async def test_session_request_retries_after_refresh(
        self, mock_request
    ) -> None:
        client, sut = _make_iaqua_system()
        mock_request.side_effect = [
            MagicMock(status_code=401),
            MagicMock(status_code=200),
        ]
        client.client_id = "old-session-id"
        client.id_token = "old-id-token"

        async def fake_refresh() -> None:
            client.client_id = "new-session-id"
            client.id_token = "new-id-token"

        with patch.object(
            client, "_refresh_auth", side_effect=fake_refresh
        ) as mock_refresh:
            await sut._send_home_screen_request()

        retry_kwargs = mock_request.call_args_list[1][1]
        retry_headers = retry_kwargs["headers"]
        retry_params = retry_kwargs["params"]

        mock_refresh.assert_awaited_once()
        assert retry_params["sessionID"] == "new-session-id"
        assert retry_headers["Authorization"] == "Bearer new-id-token"

    @patch("httpx.AsyncClient.request")
    async def test_session_request_refreshes_only_once_on_repeated_401(
        self, mock_request
    ) -> None:
        client, sut = _make_iaqua_system()
        mock_request.side_effect = [
            MagicMock(status_code=401),
            MagicMock(status_code=401),
        ]

        with (
            patch.object(
                client, "_refresh_auth", return_value=None
            ) as mock_refresh,
            pytest.raises(AqualinkServiceUnauthorizedException),
        ):
            await sut._send_home_screen_request()

        mock_refresh.assert_awaited_once()

    @patch("httpx.AsyncClient.request")
    async def test_session_request_uses_v2_url(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        mock_request.return_value.status_code = 200

        await sut._send_home_screen_request()

        called_url = mock_request.call_args[0][1]
        assert called_url.startswith(IAQUA_SESSION_URL)

    @patch("httpx.AsyncClient.request")
    async def test_session_request_sends_auth_headers(
        self, mock_request
    ) -> None:
        client, sut = _make_iaqua_system()
        mock_request.return_value.status_code = 200
        client.id_token = "test-id-token"

        await sut._send_home_screen_request()

        headers = mock_request.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer test-id-token"
        assert headers["api_key"] == AQUALINK_API_KEY

    async def test_parse_home_creates_pool_thermostat(self) -> None:
        _, sut = _make_iaqua_system()
        r = _home_response([{"pool_set_point": "86"}, {"pool_heater": "0"}])
        sut._parse_home_response(r)
        assert "pool_thermostat" in sut.devices
        assert isinstance(sut.devices["pool_thermostat"], IaquaClimate)

    async def test_parse_home_creates_spa_thermostat(self) -> None:
        _, sut = _make_iaqua_system()
        r = _home_response([{"spa_set_point": "102"}, {"spa_heater": "0"}])
        sut._parse_home_response(r)
        assert "spa_thermostat" in sut.devices
        assert isinstance(sut.devices["spa_thermostat"], IaquaClimate)

    async def test_parse_home_no_thermostat_without_heater(self) -> None:
        _, sut = _make_iaqua_system()
        r = _home_response([{"pool_set_point": "86"}])
        sut._parse_home_response(r)
        assert "pool_thermostat" not in sut.devices

    async def test_parse_home_thermostat_not_duplicated_on_reparse(
        self,
    ) -> None:
        _, sut = _make_iaqua_system()
        r = _home_response([{"pool_set_point": "86"}, {"pool_heater": "0"}])
        sut._parse_home_response(r)
        first = sut.devices["pool_thermostat"]
        sut._parse_home_response(r)
        assert sut.devices["pool_thermostat"] is first

    async def test_parse_home_creates_heatpump(self) -> None:
        _, sut = _make_iaqua_system()
        r = _home_response(
            [
                {
                    "heatpump_info": {
                        "isheatpumpPresent": True,
                        "heatpumpstatus": "off",
                        "isChillAvailable": False,
                        "heatpumpmode": "heat",
                        "heatpumptype": "4-wired",
                    }
                }
            ]
        )
        sut._parse_home_response(r)
        assert "heatpump" in sut.devices
        assert "heatpump_status" in sut.devices
        assert isinstance(sut.devices["heatpump"], IaquaHeatPump)
        assert sut.devices["heatpump"].is_on is False
        # No real choice when chill isn't available, and no alert field on
        # the get_home shape — neither entity is created.
        assert "heatpump_mode" not in sut.devices
        assert "heatpump_alert" not in sut.devices

    async def test_parse_home_creates_heatpump_mode_when_chill_available(
        self,
    ) -> None:
        _, sut = _make_iaqua_system()
        r = _home_response(
            [
                {
                    "heatpump_info": {
                        "isheatpumpPresent": True,
                        "heatpumpstatus": "enabled",
                        "isChillAvailable": True,
                        "heatpumpmode": "chill",
                        "heatpumptype": "2-wired",
                    }
                }
            ]
        )
        sut._parse_home_response(r)
        assert isinstance(sut.devices["heatpump_mode"], IaquaHeatPumpMode)
        assert sut.devices["heatpump_mode"].current_option == "chill"
        assert isinstance(sut.devices["heatpump"], IaquaHeatPump)
        assert sut.devices["heatpump"].is_on is True

    async def test_parse_home_no_heatpump_when_info_missing(self) -> None:
        _, sut = _make_iaqua_system()
        r = _home_response([{"pool_set_point": "86"}])
        sut._parse_home_response(r)
        assert "heatpump" not in sut.devices

    async def test_parse_home_heatpump_absent_removes_devices(self) -> None:
        _, sut = _make_iaqua_system()
        present = _home_response(
            [
                {
                    "heatpump_info": {
                        "isheatpumpPresent": True,
                        "heatpumpstatus": "on",
                        "isChillAvailable": True,
                        "heatpumpmode": "heat",
                        "heatpumptype": "2-wired",
                    }
                }
            ]
        )
        sut._parse_home_response(present)
        assert "heatpump" in sut.devices
        assert "heatpump_mode" in sut.devices

        absent = _home_response(
            [{"heatpump_info": {"isheatpumpPresent": False}}]
        )
        sut._parse_home_response(absent)
        assert "heatpump" not in sut.devices
        assert "heatpump_mode" not in sut.devices
        assert "heatpump_status" not in sut.devices
        assert "heatpump_alert" not in sut.devices

    @patch("httpx.AsyncClient.request")
    async def test_enable_disable_hpm_on(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        mock_request.return_value.status_code = 200
        with patch.object(sut, "_parse_hpm_command_response") as mock_parse:
            await sut.enable_disable_hpm(True)

            called_params = mock_request.call_args[1]["params"]
            assert called_params["command"] == IAQUA_COMMAND_ENABLE_DISABLE_HPM
            assert called_params["on_off_action"] == "on"
            mock_parse.assert_called_once_with(mock_request.return_value)

    @patch("httpx.AsyncClient.request")
    async def test_enable_disable_hpm_off(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        mock_request.return_value.status_code = 200
        with patch.object(sut, "_parse_hpm_command_response"):
            await sut.enable_disable_hpm(False)

            called_params = mock_request.call_args[1]["params"]
            assert called_params["on_off_action"] == "off"

    @patch("httpx.AsyncClient.request")
    async def test_switch_hpm_mode(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        mock_request.return_value.status_code = 200
        with patch.object(sut, "_parse_hpm_command_response") as mock_parse:
            await sut.switch_hpm_mode("chill")

            called_params = mock_request.call_args[1]["params"]
            assert called_params["command"] == IAQUA_COMMAND_SWITCH_HPM_MODE
            assert called_params["hpm_mode"] == "chill"
            mock_parse.assert_called_once_with(mock_request.return_value)

    @patch("httpx.AsyncClient.request")
    async def test_setpoint_hpm_temp(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        mock_request.return_value.status_code = 200
        with patch.object(sut, "_parse_hpm_command_response") as mock_parse:
            await sut.setpoint_hpm_temp({"poolheatsetpointtemp": "84"})

            called_params = mock_request.call_args[1]["params"]
            assert called_params["command"] == IAQUA_COMMAND_SETPOINT_HPM_TEMP
            assert called_params["poolheatsetpointtemp"] == "84"
            mock_parse.assert_called_once_with(mock_request.return_value)

    def test_upsert_heatpump_from_command_echo_shape(self) -> None:
        _, sut = _make_iaqua_system()
        sut.devices["pool_set_point"] = IaquaSetPoint(
            sut, {"name": "pool_set_point", "state": "80"}
        )
        sut.devices["spa_set_point"] = IaquaSetPoint(
            sut, {"name": "spa_set_point", "state": "90"}
        )
        response = MagicMock()
        response.json.return_value = {
            "serial": "SN123456",
            "device_status": "online",
            "is_error": False,
            "isHPMPresent": True,
            "HPMstatus": "on",
            "HPMmode": "heat",
            "HPMtype": "2-wired",
            "isChillAvailable": True,
            "poolheatSetPointTemp": 84,
            "spaheatSetPointTemp": 96,
            "response": "success",
            "alert_message": "",
            "status": "",
        }
        sut._parse_hpm_command_response(response)
        assert isinstance(sut.devices["heatpump"], IaquaHeatPump)
        assert sut.devices["heatpump"].is_on is True
        assert isinstance(sut.devices["heatpump_mode"], IaquaHeatPumpMode)
        assert sut.devices["heatpump_mode"].current_option == "heat"
        # No alert in this echo (empty string) — sensor must not be created.
        assert "heatpump_alert" not in sut.devices
        # pool_set_point/spa_set_point must be re-synced from the echo —
        # this is the regression this fix addresses.
        assert sut.devices["pool_set_point"].current_value == 84.0
        assert sut.devices["spa_set_point"].current_value == 96.0

    @patch("httpx.AsyncClient.request")
    async def test_setpoint_hpm_temp_resyncs_pool_set_point(
        self, mock_request
    ) -> None:
        """End-to-end reproduction of the staleness bug: writing pool_set_point
        through the HPM path must update current_value from the echo, not
        leave the pre-write value cached."""
        _, sut = _make_iaqua_system()
        sut.temp_unit = IaquaTemperatureUnit.FAHRENHEIT
        sut.devices["pool_set_point"] = IaquaSetPoint(
            sut, {"name": "pool_set_point", "state": "80"}
        )
        sut.devices["heatpump"] = IaquaHeatPump(
            sut, {"name": "heatpump", "state": "on"}
        )
        mock_request.return_value.status_code = 200
        # AsyncMock auto-creates attributes as further AsyncMocks, so a bare
        # `.json.return_value = ...` would make response.json() itself async
        # (response.json() is sync on real httpx.Response) — force it to a
        # plain MagicMock instead.
        mock_request.return_value.json = MagicMock(
            return_value={
                "isHPMPresent": True,
                "HPMstatus": "on",
                "HPMmode": "heat",
                "HPMtype": "2-wired",
                "isChillAvailable": False,
                "poolheatSetPointTemp": 86,
            }
        )

        await sut.devices["pool_set_point"].set_value(86)

        assert sut.devices["pool_set_point"].current_value == 86.0

    def test_upsert_heatpump_does_not_create_phantom_spa_set_point(
        self,
    ) -> None:
        _, sut = _make_iaqua_system()
        sut.devices["pool_set_point"] = IaquaSetPoint(
            sut, {"name": "pool_set_point", "state": "80"}
        )
        response = MagicMock()
        response.json.return_value = {
            "isHPMPresent": True,
            "HPMstatus": "on",
            "HPMmode": "heat",
            "HPMtype": "2-wired",
            "isChillAvailable": False,
            "poolheatSetPointTemp": 84,
            "spaheatSetPointTemp": 0,
        }
        sut._parse_hpm_command_response(response)
        assert "spa_set_point" not in sut.devices

    @patch("httpx.AsyncClient.request")
    async def test_setpoint_hpm_temp_invalidates_pool_chill_set_point(
        self, mock_request
    ) -> None:
        _, sut = _make_iaqua_system()
        sut.devices["pool_chill_set_point"] = IaquaSetPoint(
            sut, {"name": "pool_chill_set_point", "state": "78"}
        )
        mock_request.return_value.status_code = 200
        mock_request.return_value.json = MagicMock(
            return_value={
                "isHPMPresent": True,
                "HPMstatus": "on",
                "HPMmode": "chill",
                "HPMtype": "2-wired",
                "isChillAvailable": True,
            }
        )

        await sut.setpoint_hpm_temp({"poolchillsetpointtemp": "80"})

        assert sut.devices["pool_chill_set_point"].current_value is None

    def test_upsert_heatpump_alert_created_then_cleared(self) -> None:
        _, sut = _make_iaqua_system()

        def _echo(alert_message: str) -> MagicMock:
            response = MagicMock()
            response.json.return_value = {
                "isHPMPresent": True,
                "HPMstatus": "on",
                "HPMmode": "heat",
                "HPMtype": "2-wired",
                "isChillAvailable": False,
                "alert_message": alert_message,
            }
            return response

        sut._parse_hpm_command_response(_echo("7"))
        assert isinstance(
            sut.devices["heatpump_alert"], IaquaHeatPumpAlertSensor
        )
        assert sut.devices["heatpump_alert"].value == "7"

        sut._parse_hpm_command_response(_echo(""))
        assert "heatpump_alert" not in sut.devices

    def test_heatpump_is_on_true_when_status_enabled(self) -> None:
        _, sut = _make_iaqua_system()
        heatpump = IaquaHeatPump(sut, {"name": "heatpump", "state": "enabled"})
        assert heatpump.is_on is True

    @patch("httpx.AsyncClient.request")
    async def test_pool_set_point_routes_to_set_temps_without_heatpump(
        self, mock_request
    ) -> None:
        _, sut = _make_iaqua_system()
        sut.temp_unit = IaquaTemperatureUnit.FAHRENHEIT
        mock_request.return_value.status_code = 200
        sut.devices = {
            "pool_set_point": IaquaSetPoint(
                sut, {"name": "pool_set_point", "state": "84"}
            )
        }
        with patch.object(sut, "_parse_home_response"):
            await sut.devices["pool_set_point"].set_value(86)

            called_params = mock_request.call_args[1]["params"]
            assert called_params["command"] == "set_temps"
            assert called_params["temp1"] == "86"

    @patch("httpx.AsyncClient.request")
    async def test_pool_set_point_routes_to_hpm_temp_with_heatpump(
        self, mock_request
    ) -> None:
        _, sut = _make_iaqua_system()
        sut.temp_unit = IaquaTemperatureUnit.FAHRENHEIT
        mock_request.return_value.status_code = 200
        sut.devices = {
            "pool_set_point": IaquaSetPoint(
                sut, {"name": "pool_set_point", "state": "84"}
            ),
            "heatpump": IaquaHeatPump(sut, {"name": "heatpump", "state": "on"}),
        }
        with patch.object(sut, "_parse_hpm_command_response"):
            await sut.devices["pool_set_point"].set_value(86)

            called_params = mock_request.call_args[1]["params"]
            assert called_params["command"] == IAQUA_COMMAND_SETPOINT_HPM_TEMP
            assert called_params["poolheatsetpointtemp"] == "86"

    @patch("httpx.AsyncClient.request")
    async def test_pool_chill_set_point_always_routes_to_hpm_temp(
        self, mock_request
    ) -> None:
        _, sut = _make_iaqua_system()
        sut.temp_unit = IaquaTemperatureUnit.FAHRENHEIT
        mock_request.return_value.status_code = 200
        sut.devices = {
            "pool_chill_set_point": IaquaSetPoint(
                sut, {"name": "pool_chill_set_point", "state": "78"}
            )
        }
        with patch.object(sut, "_parse_hpm_command_response"):
            await sut.devices["pool_chill_set_point"].set_value(80)

            called_params = mock_request.call_args[1]["params"]
            assert called_params["command"] == IAQUA_COMMAND_SETPOINT_HPM_TEMP
            assert called_params["poolchillsetpointtemp"] == "80"

    # --- VSP (variable speed pump) ---

    @patch("httpx.AsyncClient.request")
    async def test_get_vsp_speed_uses_session_url(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        _vsp_mock_response(mock_request)

        await sut.get_vsp_speed(slot_id=5)

        called_url = mock_request.call_args[0][1]
        assert called_url == IAQUA_SESSION_URL
        assert called_url != IAQUA_SESSION_V1_URL

    @patch("httpx.AsyncClient.request")
    async def test_get_vsp_speed_params(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        _vsp_mock_response(mock_request)

        await sut.get_vsp_speed(slot_id=5)

        params = mock_request.call_args[1]["params"]
        assert params["command"] == IAQUA_COMMAND_GET_VSP_SPEED
        assert params["slot_id"] == "5"
        assert params["actionID"] == "command"
        assert params["serial"] == sut.serial

    @patch("httpx.AsyncClient.request")
    async def test_set_vsp_speed_uses_session_url(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        _vsp_mock_response(mock_request)

        await sut.set_vsp_speed(speed_id=4, slot_id=5)

        called_url = mock_request.call_args[0][1]
        assert called_url == IAQUA_SESSION_URL

    @patch("httpx.AsyncClient.request")
    async def test_set_vsp_speed_params(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        _vsp_mock_response(mock_request)

        await sut.set_vsp_speed(speed_id=4, slot_id=5)

        params = mock_request.call_args[1]["params"]
        assert params["command"] == IAQUA_COMMAND_SET_VSP_SPEED
        assert params["slot_id"] == "5"
        assert params["speed_id"] == "4"
        assert params["on_off_action"] == "on"
        assert params["actionID"] == "command"
        assert params["serial"] == sut.serial

    @patch("httpx.AsyncClient.request")
    async def test_vsp_request_sends_auth_headers(self, mock_request) -> None:
        client, sut = _make_iaqua_system()
        _vsp_mock_response(mock_request)
        client.id_token = "test-id-token"

        await sut.get_vsp_speed(slot_id=1)

        headers = mock_request.call_args[1]["headers"]
        assert headers["Authorization"] == "Bearer test-id-token"
        assert headers["api_key"] == AQUALINK_API_KEY

    @patch("httpx.AsyncClient.request")
    async def test_get_vsp_names_params(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        _vsp_mock_response(mock_request)

        await sut.get_vsp_names()

        params = mock_request.call_args[1]["params"]
        assert params["command"] == IAQUA_COMMAND_GET_VSP_NAMES
        assert params["actionID"] == "command"
        assert params["serial"] == sut.serial

    @patch("httpx.AsyncClient.request")
    async def test_get_vsp_appmodelserials_params(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        _vsp_mock_response(mock_request)

        await sut.get_vsp_appmodelserials()

        params = mock_request.call_args[1]["params"]
        assert params["command"] == IAQUA_COMMAND_GET_VSP_APPMODELSERIALS
        assert params["actionID"] == "command"
        assert params["serial"] == sut.serial

    async def test_is_vsp_true(self) -> None:
        _, sut = _make_iaqua_system()
        sut.data["isVSP"] = "true"
        assert sut.is_vsp is True

    async def test_is_vsp_false(self) -> None:
        _, sut = _make_iaqua_system()
        assert sut.is_vsp is False

    @patch("httpx.AsyncClient.request")
    async def test_get_master_device_list_uses_session_url(
        self, mock_request
    ) -> None:
        _, sut = _make_iaqua_system()
        _vsp_mock_response(mock_request)

        await sut.get_master_device_list()

        called_url = mock_request.call_args[0][1]
        assert called_url == IAQUA_SESSION_URL
        assert called_url != IAQUA_SESSION_V1_URL

    @patch("httpx.AsyncClient.request")
    async def test_get_master_device_list_params(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        _vsp_mock_response(mock_request)

        await sut.get_master_device_list()

        params = mock_request.call_args[1]["params"]
        assert params["command"] == IAQUA_COMMAND_GET_MASTER_DEVICE_LIST
        assert params["actionID"] == "command"
        assert params["serial"] == sut.serial

    async def test_refresh_vsp_pumps_creates_devices(self) -> None:
        _, sut = _make_iaqua_system()
        names_resp = {
            "vsp_names": [
                {"pumpId": 5, "pumpName": "Main Pump"},
                {"pumpId": 6, "pumpName": "Spa Pump"},
            ]
        }
        mdl_resp = {
            "deviceList": [
                {"id": 5, "name": "ePump 1", "isVSP": "true"},
                {"id": 6, "name": "ePump 2", "isVSP": "true"},
                {"id": 7, "name": "Non-VSP", "isVSP": "false"},
            ]
        }
        speed_resp = {
            "vsp_speedInfo": [
                {
                    "speedid": 1,
                    "speedName": "LO",
                    "speedvalue": 1500,
                    "enabled": "false",
                }
            ]
        }
        with (
            patch.object(sut, "get_vsp_names", return_value=names_resp),
            patch.object(sut, "get_master_device_list", return_value=mdl_resp),
            patch.object(sut, "get_vsp_speed", return_value=speed_resp),
        ):
            await sut._refresh_vsp_pumps()

        assert "vsp_pump_5" in sut.devices
        assert "vsp_pump_6" in sut.devices
        assert "vsp_pump_7" not in sut.devices
        pump5 = sut.devices["vsp_pump_5"]
        assert isinstance(pump5, IaquaVSPump)
        assert pump5.slot_id == 5
        assert pump5.data["slot_id"] == "5"  # DeviceData convention: str values
        assert pump5.label == "Main Pump"  # from get_vsp_names, not master list
        assert pump5._speed_presets is not None
        assert sut._vsp_discovered is True

    async def test_refresh_vsp_pumps_falls_back_to_appmodelserials(
        self,
    ) -> None:
        _, sut = _make_iaqua_system()
        names_resp = {"vsp_names": [{"pumpId": 5, "pumpName": "Main Pump"}]}
        mdl_resp = {
            "deviceList": [{"id": 99, "name": "Other", "isVSP": "false"}]
        }
        serials_resp = {
            "vsp_app_model_serials": [
                {
                    "pumpId": 5,
                    "pumpSerial": "ABC",
                    "modelName": "ePump",
                    "modelType": 1,
                    "appId": 1,
                    "appName": "iAqualink",
                }
            ]
        }
        speed_resp: dict[str, list[Any]] = {"vsp_speedInfo": []}
        with (
            patch.object(sut, "get_vsp_names", return_value=names_resp),
            patch.object(sut, "get_master_device_list", return_value=mdl_resp),
            patch.object(
                sut, "get_vsp_appmodelserials", return_value=serials_resp
            ),
            patch.object(sut, "get_vsp_speed", return_value=speed_resp),
        ):
            await sut._refresh_vsp_pumps()

        assert "vsp_pump_5" in sut.devices
        assert sut.devices["vsp_pump_5"].label == "Main Pump"
        assert sut._vsp_discovered is True

    async def test_refresh_vsp_pumps_skips_existing(self) -> None:
        _, sut = _make_iaqua_system()
        existing = IaquaVSPump(
            sut, {"name": "vsp_pump_5", "state": "1", "slot_id": "5"}
        )
        sut.devices["vsp_pump_5"] = existing
        names_resp = {"vsp_names": [{"pumpId": 5, "pumpName": "Main Pump"}]}
        mdl_resp = {
            "deviceList": [{"id": 5, "name": "ePump 1", "isVSP": "true"}]
        }
        with (
            patch.object(sut, "get_vsp_names", return_value=names_resp),
            patch.object(sut, "get_master_device_list", return_value=mdl_resp),
        ):
            await sut._refresh_vsp_pumps()

        assert sut.devices["vsp_pump_5"] is existing

    async def test_refresh_with_is_vsp_runs_discovery(self) -> None:
        _, sut = _make_iaqua_system()
        sut.data["isVSP"] = "true"
        names_resp = {"vsp_names": [{"pumpId": 5, "pumpName": "Main Pump"}]}
        mdl_resp = {
            "deviceList": [{"id": 5, "name": "ePump 1", "isVSP": "true"}]
        }
        with (
            patch.object(
                sut, "_send_home_screen_request", return_value=MagicMock()
            ),
            patch.object(
                sut, "_parse_home_response", side_effect=_set_online_for(sut)
            ),
            patch.object(
                sut,
                "_send_devices_screen_request",
                return_value=MagicMock(),
            ),
            patch.object(sut, "_parse_devices_response"),
            patch.object(
                sut,
                "_send_onetouch_screen_request",
                return_value=MagicMock(),
            ),
            patch.object(sut, "_parse_onetouch_response"),
            patch.object(sut, "get_vsp_names", return_value=names_resp),
            patch.object(sut, "get_master_device_list", return_value=mdl_resp),
            patch.object(
                sut, "get_vsp_speed", return_value={"vsp_speedInfo": []}
            ),
        ):
            await sut.refresh()

        assert "vsp_pump_5" in sut.devices
        assert isinstance(sut.devices["vsp_pump_5"], IaquaVSPump)
        assert sut._vsp_discovered is True

    async def test_refresh_without_is_vsp_skips_discovery(self) -> None:
        _, sut = _make_iaqua_system()
        assert sut.is_vsp is False

        with (
            patch.object(
                sut, "_send_home_screen_request", return_value=MagicMock()
            ),
            patch.object(
                sut, "_parse_home_response", side_effect=_set_online_for(sut)
            ),
            patch.object(
                sut,
                "_send_devices_screen_request",
                return_value=MagicMock(),
            ),
            patch.object(sut, "_parse_devices_response"),
            patch.object(
                sut,
                "_send_onetouch_screen_request",
                return_value=MagicMock(),
            ),
            patch.object(sut, "_parse_onetouch_response"),
            patch.object(sut, "get_vsp_names") as get_vsp_names,
        ):
            await sut.refresh()

        get_vsp_names.assert_not_called()
        assert sut._vsp_discovered is False
        assert not any(k.startswith("vsp_pump_") for k in sut.devices)

    async def test_refresh_vsp_pumps_empty_discovery(self) -> None:
        _, sut = _make_iaqua_system()
        with (
            patch.object(sut, "get_vsp_names", return_value={"vsp_names": []}),
            patch.object(
                sut,
                "get_master_device_list",
                return_value={"deviceList": []},
            ),
            patch.object(
                sut,
                "get_vsp_appmodelserials",
                return_value={"vsp_app_model_serials": []},
            ),
        ):
            await sut._refresh_vsp_pumps()

        assert not any(k.startswith("vsp_pump_") for k in sut.devices)
        assert sut._vsp_discovered is True

    async def test_refresh_vsp_pumps_logs_warning_on_partial_page(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        _, sut = _make_iaqua_system()
        mdl_resp = {
            "count": 1,
            "totalCount": 2,
            "deviceList": [{"id": 5, "name": "ePump 1", "isVSP": "true"}],
        }
        with (
            patch.object(sut, "get_vsp_names", return_value={"vsp_names": []}),
            patch.object(sut, "get_master_device_list", return_value=mdl_resp),
            patch.object(
                sut, "get_vsp_speed", return_value={"vsp_speedInfo": []}
            ),
            caplog.at_level(logging.WARNING, logger="iaqualink.systems.iaqua"),
        ):
            await sut._refresh_vsp_pumps()

        assert "partial page" in caplog.text

    async def test_refresh_vsp_failure_does_not_disconnect_system(
        self,
    ) -> None:
        _, sut = _make_iaqua_system()
        sut.data["isVSP"] = "true"

        with (
            patch.object(
                sut, "_send_home_screen_request", return_value=MagicMock()
            ),
            patch.object(
                sut, "_parse_home_response", side_effect=_set_online_for(sut)
            ),
            patch.object(
                sut,
                "_send_devices_screen_request",
                return_value=MagicMock(),
            ),
            patch.object(sut, "_parse_devices_response"),
            patch.object(
                sut,
                "_send_onetouch_screen_request",
                return_value=MagicMock(),
            ),
            patch.object(sut, "_parse_onetouch_response"),
            patch.object(
                sut,
                "get_vsp_names",
                side_effect=AqualinkServiceException("boom"),
            ),
        ):
            await sut.refresh()

        assert sut.status is SystemStatus.ONLINE
        assert sut._vsp_discovered is False

    async def test_refresh_calls_fetch_speed_on_subsequent_cycle(
        self,
    ) -> None:
        _, sut = _make_iaqua_system()
        sut.data["isVSP"] = "true"
        sut._vsp_discovered = True
        existing = IaquaVSPump(
            sut, {"name": "vsp_pump_5", "state": "1", "slot_id": "5"}
        )
        sut.devices["vsp_pump_5"] = existing

        with (
            patch.object(
                sut, "_send_home_screen_request", return_value=MagicMock()
            ),
            patch.object(
                sut, "_parse_home_response", side_effect=_set_online_for(sut)
            ),
            patch.object(
                sut,
                "_send_devices_screen_request",
                return_value=MagicMock(),
            ),
            patch.object(sut, "_parse_devices_response"),
            patch.object(
                sut,
                "_send_onetouch_screen_request",
                return_value=MagicMock(),
            ),
            patch.object(sut, "_parse_onetouch_response"),
            patch.object(existing, "fetch_speed") as fetch_speed,
        ):
            await sut.refresh()

        fetch_speed.assert_called_once()

    @patch("httpx.AsyncClient.request")
    async def test_stop_vsp_pump_params(self, mock_request) -> None:
        _, sut = _make_iaqua_system()
        _vsp_mock_response(mock_request)

        await sut.stop_vsp_pump(slot_id=3)

        params = mock_request.call_args[1]["params"]
        assert params["command"] == IAQUA_COMMAND_SET_VSP_SPEED
        assert params["slot_id"] == "3"
        assert params["speed_id"] == "1"
        assert params["on_off_action"] == "off"
        assert params["actionID"] == "command"
        assert params["serial"] == sut.serial

    @patch("httpx.AsyncClient.request")
    async def test_vsp_request_retries_after_reauth(self, mock_request) -> None:
        client, sut = _make_iaqua_system()
        auth_resp = MagicMock()
        auth_resp.status_code = 200
        auth_resp.json.return_value = {}

        mock_request.side_effect = [
            MagicMock(status_code=401),
            auth_resp,
        ]
        client.client_id = "old-session-id"
        client.id_token = "old-id-token"

        async def fake_refresh() -> None:
            client.client_id = "new-session-id"
            client.id_token = "new-id-token"

        with patch.object(
            client, "_refresh_auth", side_effect=fake_refresh
        ) as mock_refresh:
            await sut.get_vsp_speed(slot_id=1)

        retry_kwargs = mock_request.call_args_list[1][1]
        mock_refresh.assert_awaited_once()
        assert retry_kwargs["params"]["sessionID"] == "new-session-id"
        assert retry_kwargs["headers"]["Authorization"] == "Bearer new-id-token"
