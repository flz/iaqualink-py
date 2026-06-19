"""VR-specific system tests.

Generic AqualinkSystem contract is covered by tests/conformance/test_system.py
via the vr system_fixture; this module keeps only vr-specific behaviour
(shadow parsing, command dispatch, runtime validation, remote control,
throttle).
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
from iaqualink.systems.vr.const import (
    REMOTE_BACKWARD,
    REMOTE_ROTATE_LEFT,
    REMOTE_ROTATE_RIGHT,
    VR_STATE_CLEANING,
    VR_STATE_STOPPED,
)
from iaqualink.systems.vr.device import VrErrorSensor, VrRobot
from iaqualink.systems.vr.system import (
    VR_DEVICES_URL,
    VrSystem,
)

from ...conftest import load_fixture

VR_DATA = {
    "name": "Pool Robot",
    "serial_number": "SN42",
    "device_type": "vr",
    "id": 1,
}


@pytest.fixture
def sut(client) -> VrSystem:
    return cast(VrSystem, AqualinkSystem.from_data(client, data=VR_DATA))


def _mock_shadow(payload: dict) -> None:
    respx.get(f"{VR_DEVICES_URL}/SN42/shadow").mock(
        return_value=httpx.Response(200, json=payload)
    )


def test_registered() -> None:
    assert "vr" in AqualinkSystem.subclasses


@respx.mock
async def test_refresh_parses_shadow_and_sets_online(sut: VrSystem) -> None:
    _mock_shadow(load_fixture("vr", "shadow_get"))
    await sut.refresh()
    assert sut.status is SystemStatus.ONLINE
    assert "state" in sut.devices
    assert sut.devices["state"].data["state"] == 1
    assert "running" in sut.devices
    assert sut.devices["running"].data["state"] == 1
    assert "returning" in sut.devices
    assert sut.devices["returning"].data["state"] == 0
    assert "temperature" in sut.devices
    assert sut.devices["temperature"].data["state"] == 25
    assert "model_number" in sut.devices
    assert sut.devices["model_number"].data["state"] == 1
    assert "time_remaining_sec" in sut.devices

    robot = sut.devices["robot"]
    assert isinstance(robot, VrRobot)
    # fixture state == 1 -> cleaning.
    assert robot.activity is AqualinkRobotActivity.CLEANING
    # error scalar surfaced as snake_case error_state -> VrErrorSensor.
    assert "errorState" not in sut.devices
    assert isinstance(sut.devices["error_state"], VrErrorSensor)


@respx.mock
async def test_refresh_missing_robot_sets_offline(sut: VrSystem) -> None:
    _mock_shadow({"state": {"reported": {"equipment": {}}}})
    await sut.refresh()
    assert sut.status is SystemStatus.OFFLINE


@respx.mock
async def test_refresh_robot_not_dict_sets_offline(sut: VrSystem) -> None:
    # robot as list (wrong shape) -> OFFLINE.
    _mock_shadow({"state": {"reported": {"equipment": {"robot": []}}}})
    await sut.refresh()
    assert sut.status is SystemStatus.OFFLINE


@respx.mock
async def test_refresh_allowlists_robot_scalars(sut: VrSystem) -> None:
    # The live shadow carries config/internal scalars (schedule slots, vendor
    # counters) that must not become entities; only allowlisted scalars pass.
    _mock_shadow(
        {
            "state": {
                "reported": {
                    "equipment": {
                        "robot": {
                            "state": 1,
                            "prCyc": 1,
                            "stepper": 30,
                            "schConf0Enable": "0",
                            "logger": "0",
                            "equipmentId": "X",
                        }
                    }
                }
            }
        }
    )
    await sut.refresh()
    for kept in ("state", "prCyc", "stepper"):
        assert kept in sut.devices
    for noise in ("schConf0Enable", "logger", "equipmentId"):
        assert noise not in sut.devices


@respx.mock
async def test_refresh_malformed_shadow_sets_offline(sut: VrSystem) -> None:
    # state.reported missing entirely -> KeyError -> offline, not a crash.
    _mock_shadow({"state": {}})
    await sut.refresh()
    assert sut.status is SystemStatus.OFFLINE


@respx.mock
async def test_refresh_twice_updates_existing_devices(sut: VrSystem) -> None:
    _mock_shadow(load_fixture("vr", "shadow_get"))
    await sut.refresh()
    await sut.refresh()  # second pass updates existing device data in place
    assert sut.status is SystemStatus.ONLINE


def test_time_remaining_edge_cases(sut: VrSystem) -> None:
    compute = sut._compute_time_remaining_seconds
    # Not cleaning/returning -> 0.
    assert compute({"state": VR_STATE_STOPPED}) == 0
    # prCyc index past the durations list -> None.
    assert (
        compute(
            {
                "state": VR_STATE_CLEANING,
                "prCyc": 99,
                "cycleStartTime": 1000,
                "durations": {"floorTim": 60},
            }
        )
        is None
    )


@pytest.mark.parametrize(
    ("method", "rmt_ctrl"),
    [
        ("remote_backward", REMOTE_BACKWARD),
        ("remote_rotate_left", REMOTE_ROTATE_LEFT),
        ("remote_rotate_right", REMOTE_ROTATE_RIGHT),
    ],
)
async def test_remote_direction_commands_send_steering(
    sut: VrSystem, method: str, rmt_ctrl: int
) -> None:
    from iaqualink.systems.vr import system as sys_mod

    sut._remote_control_active = True  # already in remote mode; isolate steer
    with patch.object(sys_mod, "send_remote_steering", new=AsyncMock()) as m:
        await getattr(sut, method)()
        m.assert_awaited_once_with(
            sut.aqualink, "SN42", rmt_ctrl, namespace=sut.namespace
        )


async def test_refresh_throttled_propagates_and_status_unknown(
    sut: VrSystem,
) -> None:
    with patch.object(
        sut,
        "send_shadow_request",
        new=AsyncMock(side_effect=AqualinkServiceThrottledException),
    ):
        with pytest.raises(AqualinkServiceThrottledException):
            await sut.refresh()
    assert sut.status is SystemStatus.UNKNOWN


# --- write commands ---------------------------------------------------------


async def test_start_cleaning_dispatches_state_cleaning(sut: VrSystem) -> None:
    from iaqualink.systems.vr import system as sys_mod

    with patch.object(sys_mod, "send_set_state", new=AsyncMock()) as m:
        await sut.start_cleaning()
        m.assert_awaited_once_with(sut.aqualink, "SN42", 1, namespace="vr")


async def test_start_cleaning_with_cycle_sets_cycle_first(
    sut: VrSystem,
) -> None:
    from iaqualink.systems.vr import system as sys_mod

    with (
        patch.object(sys_mod, "send_set_state", new=AsyncMock()) as m_state,
        patch.object(sys_mod, "send_set_cycle", new=AsyncMock()) as m_cycle,
    ):
        await sut.start_cleaning(cycle=2)
        m_cycle.assert_awaited_once_with(
            sut.aqualink, "SN42", 2, namespace="vr"
        )
        m_state.assert_awaited_once_with(
            sut.aqualink, "SN42", 1, namespace="vr"
        )


async def test_stop_cleaning_dispatches_state_stopped(sut: VrSystem) -> None:
    from iaqualink.systems.vr import system as sys_mod

    with patch.object(sys_mod, "send_set_state", new=AsyncMock()) as m:
        await sut.stop_cleaning()
        m.assert_awaited_once_with(sut.aqualink, "SN42", 0, namespace="vr")


async def test_pause_cleaning_dispatches_state_paused(sut: VrSystem) -> None:
    from iaqualink.systems.vr import system as sys_mod

    with patch.object(sys_mod, "send_set_state", new=AsyncMock()) as m:
        await sut.pause_cleaning()
        m.assert_awaited_once_with(sut.aqualink, "SN42", 2, namespace="vr")


async def test_return_to_base_dispatches_state_returning(
    sut: VrSystem,
) -> None:
    from iaqualink.systems.vr import system as sys_mod

    with patch.object(sys_mod, "send_set_state", new=AsyncMock()) as m:
        await sut.return_to_base()
        m.assert_awaited_once_with(sut.aqualink, "SN42", 3, namespace="vr")


async def test_set_cycle_invalid_raises(sut: VrSystem) -> None:
    with pytest.raises(AqualinkInvalidParameterException):
        await sut.set_cycle(99)


async def test_set_runtime_extension_dispatches_stepper(
    sut: VrSystem,
) -> None:
    from iaqualink.systems.vr import system as sys_mod

    with patch.object(sys_mod, "send_set_stepper", new=AsyncMock()) as m:
        await sut.set_runtime_extension(30)
        m.assert_awaited_once_with(sut.aqualink, "SN42", 30, namespace="vr")


async def test_set_runtime_extension_negative_raises(sut: VrSystem) -> None:
    with pytest.raises(AqualinkInvalidParameterException):
        await sut.set_runtime_extension(-15)


async def test_set_runtime_extension_non_multiple_raises(
    sut: VrSystem,
) -> None:
    with pytest.raises(AqualinkInvalidParameterException):
        await sut.set_runtime_extension(10)


async def test_adjust_runtime_clamps_at_zero(sut: VrSystem) -> None:
    sut._robot_state = {"stepper": 0}
    from iaqualink.systems.vr import system as sys_mod

    with patch.object(sys_mod, "send_set_stepper", new=AsyncMock()) as m:
        new_value = await sut.adjust_runtime(-30)
        assert new_value == 0
        m.assert_awaited_once_with(sut.aqualink, "SN42", 0, namespace="vr")


async def test_adjust_runtime_non_multiple_raises(sut: VrSystem) -> None:
    with pytest.raises(AqualinkInvalidParameterException):
        await sut.adjust_runtime(10)


# --- remote control ---------------------------------------------------------


async def test_remote_forward_first_call_pauses_then_sends(
    sut: VrSystem,
) -> None:
    from iaqualink.systems.vr import system as sys_mod

    with (
        patch.object(sys_mod, "send_set_state", new=AsyncMock()) as m_state,
        patch.object(sys_mod, "send_remote_steering", new=AsyncMock()) as m_rmt,
    ):
        await sut.remote_forward()
        # First call: state=PAUSED emitted, then rmt_ctrl=FORWARD.
        m_state.assert_awaited_once_with(
            sut.aqualink, "SN42", 2, namespace="vr"
        )
        m_rmt.assert_awaited_once_with(sut.aqualink, "SN42", 1, namespace="vr")


async def test_remote_forward_second_call_no_extra_pause(
    sut: VrSystem,
) -> None:
    from iaqualink.systems.vr import system as sys_mod

    with (
        patch.object(sys_mod, "send_set_state", new=AsyncMock()) as m_state,
        patch.object(sys_mod, "send_remote_steering", new=AsyncMock()) as m_rmt,
    ):
        await sut.remote_forward()
        await sut.remote_forward()
        # state=PAUSED emitted exactly once (on first remote call only).
        m_state.assert_awaited_once_with(
            sut.aqualink, "SN42", 2, namespace="vr"
        )
        assert m_rmt.await_count == 2


async def test_remote_stop_sends_rmt_ctrl_stop_then_state_stopped(
    sut: VrSystem,
) -> None:
    from iaqualink.systems.vr import system as sys_mod

    # Put system into remote-active state first.
    sut._remote_control_active = True

    with (
        patch.object(sys_mod, "send_set_state", new=AsyncMock()) as m_state,
        patch.object(sys_mod, "send_remote_steering", new=AsyncMock()) as m_rmt,
    ):
        await sut.remote_stop()
        m_rmt.assert_awaited_once_with(sut.aqualink, "SN42", 0, namespace="vr")
        # _exit_remote_mode -> state=STOPPED.
        m_state.assert_awaited_once_with(
            sut.aqualink, "SN42", 0, namespace="vr"
        )
    # Flag cleared.
    assert sut._remote_control_active is False
