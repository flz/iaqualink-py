"""Tests for I2dRobotSystem."""

from __future__ import annotations

import unittest
from unittest.mock import patch

import httpx
import pytest
import respx
import respx.router

from iaqualink.const import AQUALINK_API_KEY
from iaqualink.exception import (
    AqualinkServiceThrottledException,
)
from iaqualink.system import SystemStatus
from iaqualink.systems.i2d_robot.const import (
    I2D_CONTROL_URL,
    I2D_REQUEST_RETURN_TO_BASE,
    I2D_REQUEST_START,
    I2D_REQUEST_STATUS,
    I2D_REQUEST_STOP,
)
from iaqualink.systems.i2d_robot.system import I2dRobotSystem

from ...base import dotstar, resp_200
from ...base_test_system import TestBaseSystem

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_SYSTEM_DATA = {
    "id": "PQR789",
    "serial_number": "ROBOT001",
    "name": "Polaris Robot",
    "device_type": "i2d_robot",
}

# Known-good 18-byte status hex (same field mapping as protocol tests):
#   [2]   = 04 → state_code = actively_cleaning
#   [3]   = 00 → error_code = no_error
#   [4]   = 0A → mode_code = 0x0A (custom_floor_and_walls_standard), canister_full=False
#   [5]   = 1E → time_remaining_min = 30
#   [6-8] = 01 00 00 → uptime_min = 1
#   [9-11]= 02 00 00 → total_hours = 2
#   [12-14]= AB CD EF → hardware_id = "abcdef"
#   [15-17]= 12 34 56 → firmware_id = "123456"
_GOOD_HEX = "AABB04000A1E010000020000ABCDEF123456"

_GOOD_RESPONSE = {
    "command": {
        "request": I2D_REQUEST_STATUS,
        "response": _GOOD_HEX,
    }
}

_BAD_REQUEST_RESPONSE = {
    "command": {
        "request": "WRONGREQUEST",
        "response": _GOOD_HEX,
    }
}

_BAD_HEX_RESPONSE = {
    "command": {
        "request": I2D_REQUEST_STATUS,
        "response": "ZZZZ",  # invalid hex
    }
}

_CONTROL_URL = I2D_CONTROL_URL.format(serial=_SYSTEM_DATA["serial_number"])


def _make_resp(body: dict) -> httpx.Response:
    return httpx.Response(status_code=200, json=body)


class TestI2dRobotSystemBase(TestBaseSystem):
    """Contract tests — base class overrides test_refresh_success to inject a
    valid hex response, then the rest of the TestBaseSystem contract applies."""

    def setUp(self) -> None:
        super().setUp()
        self.sut = I2dRobotSystem(self.client, _SYSTEM_DATA)
        self.sut_class = I2dRobotSystem

    @respx.mock
    async def test_refresh_success(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(_make_resp(_GOOD_RESPONSE))
        await self.sut.refresh()
        assert self.sut.status is SystemStatus.ONLINE


class TestI2dRobotSystemRefresh(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        from iaqualink.client import AqualinkClient

        self.client = AqualinkClient("foo", "bar")
        self.addAsyncCleanup(self.client.close)
        self.sut = I2dRobotSystem(self.client, _SYSTEM_DATA)

    @respx.mock
    async def test_refresh_online_status(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(_make_resp(_GOOD_RESPONSE))
        await self.sut.refresh()
        assert self.sut.status is SystemStatus.ONLINE

    @respx.mock
    async def test_refresh_populates_devices(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(_make_resp(_GOOD_RESPONSE))
        await self.sut.refresh()
        assert "state" in self.sut.devices
        assert "error" in self.sut.devices
        assert "mode" in self.sut.devices
        assert "time_remaining_min" in self.sut.devices
        assert "uptime_minutes" in self.sut.devices
        assert "total_hours" in self.sut.devices
        assert "hardware_id" in self.sut.devices
        assert "firmware_id" in self.sut.devices
        assert "canister_full" in self.sut.devices
        assert "running" in self.sut.devices
        assert "model_number" in self.sut.devices

    @respx.mock
    async def test_refresh_state_values(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(_make_resp(_GOOD_RESPONSE))
        await self.sut.refresh()
        assert self.sut.devices["state"].value == "actively_cleaning"
        assert self.sut.devices["error"].value == "no_error"
        assert (
            self.sut.devices["mode"].value == "custom_floor_and_walls_standard"
        )
        assert self.sut.devices["time_remaining_min"].value == "30"
        assert self.sut.devices["uptime_minutes"].value == "1"
        assert self.sut.devices["total_hours"].value == "2"
        assert self.sut.devices["hardware_id"].value == "abcdef"
        assert self.sut.devices["firmware_id"].value == "123456"

    @respx.mock
    async def test_refresh_binary_sensors(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(_make_resp(_GOOD_RESPONSE))
        await self.sut.refresh()
        # actively_cleaning (0x04) is in _ACTIVE_STATE_CODES → running=True
        assert self.sut.devices["running"].is_on is True
        # canister_full: high nibble of 0x0A = 0 → False
        assert self.sut.devices["canister_full"].is_on is False

    @respx.mock
    async def test_refresh_model_number(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(_make_resp(_GOOD_RESPONSE))
        await self.sut.refresh()
        assert self.sut.devices["model_number"].value == "PQR789"

    @respx.mock
    async def test_refresh_bad_command_request_goes_offline(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(_make_resp(_BAD_REQUEST_RESPONSE))
        await self.sut.refresh()
        assert self.sut.status is SystemStatus.OFFLINE

    @respx.mock
    async def test_refresh_bad_hex_goes_offline(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(_make_resp(_BAD_HEX_RESPONSE))
        await self.sut.refresh()
        assert self.sut.status is SystemStatus.OFFLINE

    async def test_refresh_throttled_propagates(self) -> None:
        with patch.object(
            self.sut,
            "_post_command",
            side_effect=AqualinkServiceThrottledException("throttled"),
        ):
            with pytest.raises(AqualinkServiceThrottledException):
                await self.sut.refresh()
        assert self.sut.status is SystemStatus.UNKNOWN

    @respx.mock
    async def test_refresh_updates_existing_devices(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(_make_resp(_GOOD_RESPONSE))
        await self.sut.refresh()
        first_state_device = self.sut.devices["state"]
        await self.sut.refresh()
        # Same object, updated in-place
        assert self.sut.devices["state"] is first_state_device

    @respx.mock
    async def test_refresh_request_uses_status_hex(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        route = respx_mock.route(dotstar).mock(_make_resp(_GOOD_RESPONSE))
        await self.sut.refresh()
        assert route.called
        request = route.calls[0].request
        import json

        body = json.loads(request.content)
        assert body["params"] == f"request={I2D_REQUEST_STATUS}"

    @respx.mock
    async def test_refresh_request_uses_api_key_header(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        route = respx_mock.route(dotstar).mock(_make_resp(_GOOD_RESPONSE))
        await self.sut.refresh()
        request = route.calls[0].request
        assert request.headers.get("api_key") == AQUALINK_API_KEY


class TestI2dRobotSystemWriteCommands(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        from iaqualink.client import AqualinkClient

        self.client = AqualinkClient("foo", "bar")
        self.addAsyncCleanup(self.client.close)
        self.sut = I2dRobotSystem(self.client, _SYSTEM_DATA)

    @respx.mock
    async def test_start_cleaning_sends_correct_hex(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        route = respx_mock.route(dotstar).mock(resp_200)
        await self.sut.start_cleaning()
        import json

        body = json.loads(route.calls[0].request.content)
        assert body["params"] == f"request={I2D_REQUEST_START}"

    @respx.mock
    async def test_stop_cleaning_sends_correct_hex(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        route = respx_mock.route(dotstar).mock(resp_200)
        await self.sut.stop_cleaning()
        import json

        body = json.loads(route.calls[0].request.content)
        assert body["params"] == f"request={I2D_REQUEST_STOP}"

    @respx.mock
    async def test_return_to_base_sends_correct_hex(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        route = respx_mock.route(dotstar).mock(resp_200)
        await self.sut.return_to_base()
        import json

        body = json.loads(route.calls[0].request.content)
        assert body["params"] == f"request={I2D_REQUEST_RETURN_TO_BASE}"

    @respx.mock
    async def test_write_uses_control_url(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        route = respx_mock.route(url=_CONTROL_URL).mock(resp_200)
        await self.sut.start_cleaning()
        assert route.called
