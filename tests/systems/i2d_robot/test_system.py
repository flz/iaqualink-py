"""i2d_robot-specific tests for I2dRobotSystem.

Generic AqualinkSystem contract behaviour (refresh success/online status,
service exception, throttling, unauthorized, reauth retry) is covered by the
conformance suite via ``i2d_robot_system_factories``. This module keeps only
the i2d_robot-specific parsing and command-wire assertions.
"""

from __future__ import annotations

import json
from typing import cast
from unittest.mock import patch

import httpx
import pytest
import respx
import respx.router

from iaqualink.client import AqualinkClient
from iaqualink.const import AQUALINK_API_KEY
from iaqualink.device import AqualinkBinarySensor, AqualinkSensor
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
)
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.i2d_robot.const import (
    I2D_CONTROL_URL,
    I2D_REQUEST_RETURN_TO_BASE,
    I2D_REQUEST_START,
    I2D_REQUEST_STATUS,
    I2D_REQUEST_STOP,
)
from iaqualink.systems.i2d_robot.system import I2dRobotSystem

from ...conftest import dotstar, resp_200

# ---------------------------------------------------------------------------
# Fixtures / sample data
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
    "command": {"request": I2D_REQUEST_STATUS, "response": _GOOD_HEX}
}
_BAD_REQUEST_RESPONSE = {
    "command": {"request": "WRONGREQUEST", "response": _GOOD_HEX}
}
_BAD_HEX_RESPONSE = {
    "command": {"request": I2D_REQUEST_STATUS, "response": "ZZZZ"}
}

_CONTROL_URL = I2D_CONTROL_URL.format(serial=_SYSTEM_DATA["serial_number"])


@pytest.fixture
def sut(client: AqualinkClient) -> I2dRobotSystem:
    return I2dRobotSystem(client, _SYSTEM_DATA)


def _make_resp(body: dict) -> httpx.Response:
    return httpx.Response(status_code=200, json=body)


def test_registered() -> None:
    assert "i2d_robot" in AqualinkSystem.subclasses


def test_from_data_returns_i2d_robot_system(client: AqualinkClient) -> None:
    system = AqualinkSystem.from_data(client, _SYSTEM_DATA)
    assert isinstance(system, I2dRobotSystem)


# ---------------------------------------------------------------------------
# Refresh / parsing
# ---------------------------------------------------------------------------


@respx.mock
async def test_refresh_populates_devices(
    sut: I2dRobotSystem, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(_make_resp(_GOOD_RESPONSE))
    await sut.refresh()
    for name in (
        "state",
        "error",
        "mode",
        "time_remaining_min",
        "uptime_minutes",
        "total_hours",
        "hardware_id",
        "firmware_id",
        "canister_full",
        "running",
        "model_number",
    ):
        assert name in sut.devices


@respx.mock
async def test_refresh_state_values(
    sut: I2dRobotSystem, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(_make_resp(_GOOD_RESPONSE))
    await sut.refresh()

    def sensor(name: str) -> AqualinkSensor:
        return cast(AqualinkSensor, sut.devices[name])

    assert sensor("state").value == "actively_cleaning"
    assert sensor("error").value == "no_error"
    assert sensor("mode").value == "custom_floor_and_walls_standard"
    assert sensor("time_remaining_min").value == 30
    assert sensor("uptime_minutes").value == 1
    assert sensor("total_hours").value == 2
    assert sensor("hardware_id").value == "abcdef"
    assert sensor("firmware_id").value == "123456"


@respx.mock
async def test_refresh_raises_on_invalid_json(
    sut: I2dRobotSystem, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(
        return_value=httpx.Response(200, content=b"<<not json>>")
    )
    with pytest.raises(AqualinkServiceException):
        await sut.refresh()


@respx.mock
async def test_refresh_raises_on_non_dict_response(
    sut: I2dRobotSystem, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(
        return_value=httpx.Response(200, json=[1, 2, 3])
    )
    with pytest.raises(AqualinkServiceException):
        await sut.refresh()


@respx.mock
async def test_refresh_binary_sensors(
    sut: I2dRobotSystem, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(_make_resp(_GOOD_RESPONSE))
    await sut.refresh()
    # actively_cleaning (0x04) is in _ACTIVE_STATE_CODES → running=True
    assert cast(AqualinkBinarySensor, sut.devices["running"]).is_on is True
    # canister_full: high nibble of 0x0A = 0 → False
    assert (
        cast(AqualinkBinarySensor, sut.devices["canister_full"]).is_on is False
    )


@respx.mock
async def test_refresh_model_number(
    sut: I2dRobotSystem, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(_make_resp(_GOOD_RESPONSE))
    await sut.refresh()
    assert cast(AqualinkSensor, sut.devices["model_number"]).value == "PQR789"


@respx.mock
async def test_refresh_bad_command_request_goes_offline(
    sut: I2dRobotSystem, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(_make_resp(_BAD_REQUEST_RESPONSE))
    await sut.refresh()
    assert sut.status is SystemStatus.OFFLINE


@respx.mock
async def test_refresh_bad_hex_goes_offline(
    sut: I2dRobotSystem, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(_make_resp(_BAD_HEX_RESPONSE))
    await sut.refresh()
    assert sut.status is SystemStatus.OFFLINE


async def test_refresh_throttled_propagates(sut: I2dRobotSystem) -> None:
    with (
        patch.object(
            sut,
            "_post_command",
            side_effect=AqualinkServiceThrottledException("throttled"),
        ),
        pytest.raises(AqualinkServiceThrottledException),
    ):
        await sut.refresh()
    assert sut.status is SystemStatus.UNKNOWN


@respx.mock
async def test_refresh_updates_existing_devices(
    sut: I2dRobotSystem, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(_make_resp(_GOOD_RESPONSE))
    await sut.refresh()
    first_state_device = sut.devices["state"]
    await sut.refresh()
    # Same object, updated in-place.
    assert sut.devices["state"] is first_state_device


@respx.mock
async def test_refresh_request_uses_status_hex(
    sut: I2dRobotSystem, respx_mock: respx.router.MockRouter
) -> None:
    route = respx_mock.route(dotstar).mock(_make_resp(_GOOD_RESPONSE))
    await sut.refresh()
    assert route.called
    body = json.loads(route.calls[0].request.content)
    assert body["params"] == f"request={I2D_REQUEST_STATUS}"


@respx.mock
async def test_refresh_request_uses_api_key_header(
    sut: I2dRobotSystem, respx_mock: respx.router.MockRouter
) -> None:
    route = respx_mock.route(dotstar).mock(_make_resp(_GOOD_RESPONSE))
    await sut.refresh()
    request = route.calls[0].request
    assert request.headers.get("api_key") == AQUALINK_API_KEY


# ---------------------------------------------------------------------------
# Write commands
# ---------------------------------------------------------------------------


@respx.mock
async def test_start_cleaning_sends_correct_hex(
    sut: I2dRobotSystem, respx_mock: respx.router.MockRouter
) -> None:
    route = respx_mock.route(dotstar).mock(resp_200)
    await sut.start_cleaning()
    body = json.loads(route.calls[0].request.content)
    assert body["params"] == f"request={I2D_REQUEST_START}"


@respx.mock
async def test_stop_cleaning_sends_correct_hex(
    sut: I2dRobotSystem, respx_mock: respx.router.MockRouter
) -> None:
    route = respx_mock.route(dotstar).mock(resp_200)
    await sut.stop_cleaning()
    body = json.loads(route.calls[0].request.content)
    assert body["params"] == f"request={I2D_REQUEST_STOP}"


@respx.mock
async def test_return_to_base_sends_correct_hex(
    sut: I2dRobotSystem, respx_mock: respx.router.MockRouter
) -> None:
    route = respx_mock.route(dotstar).mock(resp_200)
    await sut.return_to_base()
    body = json.loads(route.calls[0].request.content)
    assert body["params"] == f"request={I2D_REQUEST_RETURN_TO_BASE}"


@respx.mock
async def test_write_uses_control_url(
    sut: I2dRobotSystem, respx_mock: respx.router.MockRouter
) -> None:
    route = respx_mock.route(url=_CONTROL_URL).mock(resp_200)
    await sut.start_cleaning()
    assert route.called
