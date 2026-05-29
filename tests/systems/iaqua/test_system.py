from __future__ import annotations

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
from iaqualink.systems.iaqua.device import IaquaClimate, IaquaOneTouchSwitch
from iaqualink.systems.iaqua.enums import IaquaSystemType, IaquaTemperatureUnit
from iaqualink.systems.iaqua.system import (
    IAQUA_COMMAND_SET_ONETOUCH,
    IAQUA_SESSION_URL,
)

from ...conftest import dotstar, resp_200

_SYSTEM_DATA = {
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


def _make_iaqua_system() -> tuple[AqualinkClient, AqualinkSystem]:
    client = AqualinkClient("foo", "bar")
    sut = AqualinkSystem.from_data(client, data={**_SYSTEM_DATA})
    return client, sut


def _set_online_for(sut: AqualinkSystem):
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
