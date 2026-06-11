"""Cyclonext-specific system tests.

Generic AqualinkSystem contract is covered by tests/conformance/test_system.py
via the cyclonext system_fixture; this module keeps only cyclonext-specific
behaviour (shadow parsing, command dispatch, runtime validation, throttle).
"""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from iaqualink.enums import AqualinkRobotActivity
from iaqualink.exception import (
    AqualinkInvalidParameterException,
    AqualinkServiceThrottledException,
)
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.cyclonext.device import CyclonextRobot
from iaqualink.systems.cyclonext.system import (
    CYCLONEXT_DEVICES_URL,
    CyclonextSystem,
)

from ...conftest import load_fixture

CYCLONEXT_DATA = {
    "name": "Pool Robot",
    "serial_number": "SN42",
    "device_type": "cyclonext",
    "id": 1,
}


@pytest.fixture
def sut(client) -> CyclonextSystem:
    return cast(
        CyclonextSystem, AqualinkSystem.from_data(client, data=CYCLONEXT_DATA)
    )


def _mock_shadow(payload: dict) -> None:
    respx.get(f"{CYCLONEXT_DEVICES_URL}/SN42/shadow").mock(
        return_value=httpx.Response(200, json=payload)
    )


def test_registered_in_subclasses() -> None:
    assert "cyclonext" in AqualinkSystem.subclasses


@respx.mock
async def test_refresh_parses_shadow_and_sets_online(
    sut: CyclonextSystem,
) -> None:
    _mock_shadow(load_fixture("cyclonext", "shadow_get"))
    await sut.refresh()
    assert sut.status is SystemStatus.ONLINE
    assert "mode" in sut.devices
    assert sut.devices["mode"].data["state"] == 1
    assert "error_code" in sut.devices
    assert sut.devices["error_code"].data["state"] == 0
    assert "ebox_sn" in sut.devices
    assert sut.devices["ebox_sn"].data["state"] == "EBOX42"
    assert "control_box_vr" in sut.devices
    assert sut.devices["control_box_vr"].data["state"] == "cb-2.1"
    assert "running" in sut.devices
    assert sut.devices["running"].data["state"] == 1
    assert "model_number" in sut.devices
    assert "time_remaining_sec" in sut.devices

    robot = sut.devices["robot"]
    assert isinstance(robot, CyclonextRobot)
    # fixture mode == 1 -> cleaning.
    assert robot.activity is AqualinkRobotActivity.CLEANING


@respx.mock
async def test_refresh_missing_robot_sets_offline(
    sut: CyclonextSystem,
) -> None:
    # robot list contains only null entries → offline.
    _mock_shadow({"state": {"reported": {"equipment": {"robot": [None]}}}})
    await sut.refresh()
    assert sut.status is SystemStatus.OFFLINE


async def test_refresh_throttled_sets_unknown_and_propagates(
    sut: CyclonextSystem,
) -> None:
    with patch.object(sut, "send_shadow_request") as mock_req:
        mock_req.side_effect = AqualinkServiceThrottledException
        with pytest.raises(AqualinkServiceThrottledException):
            await sut.refresh()
    assert sut.status is SystemStatus.UNKNOWN


async def test_start_cleaning_dispatches_mode_start(
    sut: CyclonextSystem,
) -> None:
    from iaqualink.systems.cyclonext import system as sys_mod

    with (
        patch.object(sys_mod, "send_set_mode", new=AsyncMock()) as m_mode,
        patch.object(sys_mod, "send_set_cycle", new=AsyncMock()) as m_cycle,
    ):
        await sut.start_cleaning()
        m_mode.assert_awaited_once_with(sut.aqualink, "SN42", mode=1)
        m_cycle.assert_not_awaited()


async def test_start_cleaning_with_cycle_sets_cycle_first(
    sut: CyclonextSystem,
) -> None:
    from iaqualink.systems.cyclonext import system as sys_mod

    with (
        patch.object(sys_mod, "send_set_mode", new=AsyncMock()) as m_mode,
        patch.object(sys_mod, "send_set_cycle", new=AsyncMock()) as m_cycle,
    ):
        await sut.start_cleaning(cycle=3)
        m_cycle.assert_awaited_once_with(sut.aqualink, "SN42", cycle=3)
        m_mode.assert_awaited_once_with(sut.aqualink, "SN42", mode=1)


async def test_stop_cleaning_dispatches_mode_stop(
    sut: CyclonextSystem,
) -> None:
    from iaqualink.systems.cyclonext import system as sys_mod

    with patch.object(sys_mod, "send_set_mode", new=AsyncMock()) as m:
        await sut.stop_cleaning()
        m.assert_awaited_once_with(sut.aqualink, "SN42", mode=0)


async def test_pause_cleaning_dispatches_mode_pause(
    sut: CyclonextSystem,
) -> None:
    from iaqualink.systems.cyclonext import system as sys_mod

    with patch.object(sys_mod, "send_set_mode", new=AsyncMock()) as m:
        await sut.pause_cleaning()
        m.assert_awaited_once_with(sut.aqualink, "SN42", mode=2)


async def test_set_runtime_extension_dispatches_stepper(
    sut: CyclonextSystem,
) -> None:
    from iaqualink.systems.cyclonext import system as sys_mod

    with patch.object(sys_mod, "send_set_stepper", new=AsyncMock()) as m:
        await sut.set_runtime_extension(30)
        m.assert_awaited_once_with(sut.aqualink, "SN42", minutes=30)


async def test_set_runtime_extension_negative_raises(
    sut: CyclonextSystem,
) -> None:
    with pytest.raises(AqualinkInvalidParameterException):
        await sut.set_runtime_extension(-15)


async def test_set_runtime_extension_non_multiple_raises(
    sut: CyclonextSystem,
) -> None:
    with pytest.raises(AqualinkInvalidParameterException):
        await sut.set_runtime_extension(10)


async def test_adjust_runtime_clamps_at_zero(sut: CyclonextSystem) -> None:
    # Seed internal cache so adjust_runtime has a baseline.
    sut._robot_state = {"stepper": 0}
    from iaqualink.systems.cyclonext import system as sys_mod

    with patch.object(sys_mod, "send_set_stepper", new=AsyncMock()) as m:
        new_value = await sut.adjust_runtime(-30)
        assert new_value == 0
        m.assert_awaited_once_with(sut.aqualink, "SN42", minutes=0)


async def test_adjust_runtime_non_multiple_raises(
    sut: CyclonextSystem,
) -> None:
    with pytest.raises(AqualinkInvalidParameterException):
        await sut.adjust_runtime(10)


async def test_remote_forward_dispatches_mode_remote_direction_forward(
    sut: CyclonextSystem,
) -> None:
    from iaqualink.systems.cyclonext import system as sys_mod

    with patch.object(sys_mod, "send_set_remote_state", new=AsyncMock()) as m:
        await sut.remote_forward()
        m.assert_awaited_once_with(sut.aqualink, "SN42", mode=2, direction=1)


async def test_remote_stop_dispatches_mode_remote_direction_stop(
    sut: CyclonextSystem,
) -> None:
    from iaqualink.systems.cyclonext import system as sys_mod

    with patch.object(sys_mod, "send_set_remote_state", new=AsyncMock()) as m:
        await sut.remote_stop()
        m.assert_awaited_once_with(sut.aqualink, "SN42", mode=2, direction=0)


async def test_lift_eject_dispatches_mode_lift_direction_eject(
    sut: CyclonextSystem,
) -> None:
    from iaqualink.systems.cyclonext import system as sys_mod

    with patch.object(sys_mod, "send_set_remote_state", new=AsyncMock()) as m:
        await sut.lift_eject()
        m.assert_awaited_once_with(sut.aqualink, "SN42", mode=3, direction=5)
