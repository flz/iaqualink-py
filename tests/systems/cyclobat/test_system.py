from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from iaqualink.device import AqualinkSensor
from iaqualink.enums import AqualinkRobotActivity
from iaqualink.exception import AqualinkServiceThrottledException
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.cyclobat.device import CyclobatRobot
from iaqualink.systems.cyclobat.system import (
    CYCLOBAT_DEVICES_URL,
    CyclobatSystem,
)

from ...conftest import load_fixture

CYCLOBAT_DATA = {
    "id": "CV3000",
    "serial_number": "SN42",
    "device_type": "cyclobat",
    "name": "Pool Robot",
}


@pytest.fixture
def sut(client) -> CyclobatSystem:
    return cast(
        CyclobatSystem, AqualinkSystem.from_data(client, data=CYCLOBAT_DATA)
    )


def _mock_shadow(payload: dict) -> None:
    respx.get(f"{CYCLOBAT_DEVICES_URL}/SN42/shadow").mock(
        return_value=httpx.Response(200, json=payload)
    )


@respx.mock
async def test_refresh_parses_shadow_and_sets_online(
    sut: CyclobatSystem,
) -> None:
    _mock_shadow(load_fixture("cyclobat", "shadow_get"))
    await sut.refresh()
    assert sut.status is SystemStatus.ONLINE
    assert "battery_percentage" in sut.devices
    battery = cast(AqualinkSensor, sut.devices["battery_percentage"])
    assert battery.value == 87
    assert "running" in sut.devices

    robot = sut.devices["robot"]
    assert isinstance(robot, CyclobatRobot)
    # fixture main.state == 1 -> cleaning.
    assert robot.activity is AqualinkRobotActivity.CLEANING
    assert sut.devices["running"].data["state"] == 1
    assert "model_number" in sut.devices


@respx.mock
async def test_total_runtime_is_minutes_not_hours(sut: CyclobatSystem) -> None:
    # stats.totRunTime is MINUTES; the key must be unit-neutral, not
    # `total_hours` (which implies a different unit).
    _mock_shadow(load_fixture("cyclobat", "shadow_get"))
    await sut.refresh()
    assert "total_runtime" in sut.devices
    assert "total_hours" not in sut.devices
    runtime = cast(AqualinkSensor, sut.devices["total_runtime"])
    assert runtime.unit_of_measurement == "min"
    assert runtime.device_class is None
    assert runtime.state_class == "total_increasing"
    assert runtime.value == 1234


@respx.mock
async def test_refresh_missing_robot_sets_offline(
    sut: CyclobatSystem,
) -> None:
    _mock_shadow({"state": {"reported": {}}})
    await sut.refresh()
    assert sut.status is SystemStatus.OFFLINE


async def test_refresh_skips_rest_when_ws_state_fresh(
    sut: CyclobatSystem,
) -> None:
    sut._ws_enabled = True
    with (
        patch.object(sut, "_ws_state_fresh", return_value=True),
        patch.object(sut, "send_shadow_request") as mock_req,
    ):
        await sut.refresh()
    mock_req.assert_not_called()


@respx.mock
async def test_refresh_polls_rest_when_ws_disabled(
    sut: CyclobatSystem,
) -> None:
    # WS fresh but disabled -> must still poll REST.
    sut._ws_enabled = False
    _mock_shadow(load_fixture("cyclobat", "shadow_get"))
    with patch.object(sut, "_ws_state_fresh", return_value=True):
        await sut.refresh()
    assert sut.status is SystemStatus.ONLINE


@respx.mock
async def test_apply_robot_delta_merges_and_rederives(
    sut: CyclobatSystem,
) -> None:
    # A WS StateStreamer delta must deep-merge onto cached state and
    # re-derive devices, leaving sibling fields untouched.
    _mock_shadow(load_fixture("cyclobat", "shadow_get"))
    await sut.refresh()
    assert cast(AqualinkSensor, sut.devices["battery_percentage"]).value == 87

    sut._apply_robot_delta({"battery": {"userChargePerc": 50}})

    assert cast(AqualinkSensor, sut.devices["battery_percentage"]).value == 50
    # deep_merge preserved a field the delta didn't mention.
    assert "total_runtime" in sut.devices


async def test_extract_robot_handles_dotted_ws_key(
    sut: CyclobatSystem,
) -> None:
    # WS Authorization/StateStreamer payloads dot-key the robot as
    # equipment["robot.1"] rather than nesting it under equipment.robot.
    reported = load_fixture("cyclobat", "shadow_get")["state"]["reported"]
    robot = reported["equipment"].pop("robot")
    reported["equipment"]["robot.1"] = robot

    assert sut._extract_robot(reported) is robot

    sut._apply_reported_state(reported)
    assert cast(AqualinkSensor, sut.devices["battery_percentage"]).value == 87


async def test_refresh_throttled_sets_unknown_and_propagates(
    sut: CyclobatSystem,
) -> None:
    with patch.object(sut, "send_shadow_request") as mock_req:
        mock_req.side_effect = AqualinkServiceThrottledException
        with pytest.raises(AqualinkServiceThrottledException):
            await sut.refresh()
    assert sut.status is SystemStatus.UNKNOWN


async def test_start_cleaning_calls_send_set_ctrl(sut: CyclobatSystem) -> None:
    from iaqualink.systems.cyclobat import system as sys_mod

    with patch.object(sys_mod, "send_set_ctrl", new=AsyncMock()) as m:
        await sut.start_cleaning()
        m.assert_awaited_once_with(sut.aqualink, "SN42", 1)


async def test_stop_cleaning_calls_send_set_ctrl(sut: CyclobatSystem) -> None:
    from iaqualink.systems.cyclobat import system as sys_mod

    with patch.object(sys_mod, "send_set_ctrl", new=AsyncMock()) as m:
        await sut.stop_cleaning()
        m.assert_awaited_once_with(sut.aqualink, "SN42", 0)


async def test_return_to_base_calls_send_set_ctrl(
    sut: CyclobatSystem,
) -> None:
    from iaqualink.systems.cyclobat import system as sys_mod

    with patch.object(sys_mod, "send_set_ctrl", new=AsyncMock()) as m:
        await sut.return_to_base()
        m.assert_awaited_once_with(sut.aqualink, "SN42", 3)
