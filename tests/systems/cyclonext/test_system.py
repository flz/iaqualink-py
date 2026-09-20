"""Cyclonext-specific system tests.

Generic AqualinkSystem contract is covered by tests/conformance/test_system.py
via the cyclonext system_fixture; this module keeps only cyclonext-specific
behaviour (shadow parsing, command dispatch, runtime validation, throttle).
"""

from __future__ import annotations

import json
import time
from typing import cast
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx

from iaqualink.device import AqualinkBinarySensor
from iaqualink.enums import AqualinkRobotActivity
from iaqualink.exception import (
    AqualinkInvalidParameterException,
    AqualinkServiceThrottledException,
)
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.cyclonext.const import (
    DIRECTION_BACKWARD,
    DIRECTION_LIFT_ROTATE_LEFT,
    DIRECTION_LIFT_ROTATE_RIGHT,
    DIRECTION_ROTATE_LEFT,
    DIRECTION_ROTATE_RIGHT,
    DIRECTION_STOP,
    MODE_LIFT,
    MODE_REMOTE,
)
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
async def test_refresh_surfaces_full_errors_dict(
    sut: CyclonextSystem,
) -> None:
    # Every scalar under the robot's `errors` block becomes an `error_<key>`
    # sensor, not just `code`. Sibling fields (e.g. timestamp) are preserved.
    payload = load_fixture("cyclonext", "shadow_get")
    robot = next(
        r
        for r in payload["state"]["reported"]["equipment"]["robot"]
        if isinstance(r, dict)
    )
    robot["errors"] = {"code": 107, "timestamp": 1783590606}
    _mock_shadow(payload)
    await sut.refresh()
    assert sut.devices["error_code"].data["state"] == 107
    assert "error_timestamp" in sut.devices
    assert sut.devices["error_timestamp"].data["state"] == 1783590606
    assert sut.devices["error_timestamp"].entity_category == "diagnostic"


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


async def test_set_cycle_dispatches(sut: CyclonextSystem) -> None:
    from iaqualink.systems.cyclonext import system as sys_mod

    with patch.object(sys_mod, "send_set_cycle", new=AsyncMock()) as m:
        await sut.set_cycle(2)
        m.assert_awaited_once_with(sut.aqualink, "SN42", cycle=2)


@pytest.mark.parametrize(
    ("method", "mode", "direction"),
    [
        ("remote_backward", MODE_REMOTE, DIRECTION_BACKWARD),
        ("remote_rotate_left", MODE_REMOTE, DIRECTION_ROTATE_LEFT),
        ("remote_rotate_right", MODE_REMOTE, DIRECTION_ROTATE_RIGHT),
        ("lift_rotate_left", MODE_LIFT, DIRECTION_LIFT_ROTATE_LEFT),
        ("lift_rotate_right", MODE_LIFT, DIRECTION_LIFT_ROTATE_RIGHT),
        ("lift_stop", MODE_LIFT, DIRECTION_STOP),
    ],
)
async def test_remote_lift_commands_dispatch(
    sut: CyclonextSystem, method: str, mode: int, direction: int
) -> None:
    from iaqualink.systems.cyclonext import system as sys_mod

    with patch.object(sys_mod, "send_set_remote_state", new=AsyncMock()) as m:
        await getattr(sut, method)()
        m.assert_awaited_once_with(
            sut.aqualink, "SN42", mode=mode, direction=direction
        )


@respx.mock
async def test_refresh_malformed_shadow_sets_offline(
    sut: CyclonextSystem,
) -> None:
    # state.reported missing entirely -> KeyError -> offline, not a crash.
    _mock_shadow({"state": {}})
    await sut.refresh()
    assert sut.status is SystemStatus.OFFLINE


def test_extract_robot_dict_shape_and_missing(sut: CyclonextSystem) -> None:
    robot = {"mode": 1}
    # Some payloads nest the robot as a bare dict under equipment.robot.
    assert sut._extract_robot({"equipment": {"robot": robot}}) is robot
    # No robot present -> None.
    assert sut._extract_robot({"equipment": {}}) is None


def test_time_remaining_unknown_cycle_returns_none(
    sut: CyclonextSystem,
) -> None:
    # Active cycle but unknown cycle id -> duration unknown -> None.
    assert (
        sut._compute_time_remaining_seconds(
            {"mode": 1, "cycle": 999, "cycleStartTime": 1000, "durations": {}}
        )
        is None
    )


def test_rebuild_robot_devices_allowlists_scalars(
    sut: CyclonextSystem,
) -> None:
    # The live shadow carries config/internal scalars (schedule slots, vendor
    # counters) that must not become entities; only allowlisted scalars pass.
    sut._robot_state = {
        "mode": 1,
        "cycle": 2,
        "stepper": 30,
        "schConf0Enable": "0",
        "logger": "0",
        "stepperAdjTime": "15",
        "equipmentId": "ND22010130",
    }
    sut._rebuild_robot_devices()
    for kept in ("mode", "cycle", "stepper"):
        assert kept in sut.devices
    for noise in ("schConf0Enable", "logger", "stepperAdjTime", "equipmentId"):
        assert noise not in sut.devices


# --- WebSocket state subscription (reduce polling) -------------------------
# Protocol captured from the vendor app: Authorization `subscribe` on connect,
# full state in the Authorization ack, then StateStreamer `StateReported`
# deltas (`desired` frames are command echoes and are ignored).

_AUTH_FULL_FRAME = {
    "service": "Authorization",
    "target": "SN42",
    "namespace": "authorization",
    "payload": {
        "robot": {
            "state": {
                "reported": {
                    "equipment": {
                        "robot.1": {
                            "mode": 0,
                            "cycle": 1,
                            "stepper": 0,
                            "durations": {"waterTim": 45, "smartTim": 0},
                        }
                    }
                }
            }
        }
    },
}

_DELTA_FRAME = {
    "service": "StateStreamer",
    "event": "StateReported",
    "version": 1,
    "payload": {"state": {"reported": {"equipment": {"robot.1": {"mode": 1}}}}},
}

_ECHO_FRAME = {
    "service": "StateStreamer",
    "event": "StateReported",
    "payload": {"state": {"desired": {"equipment": {"robot.1": {"mode": 1}}}}},
}


class TestCyclonextWsSubscription:
    def test_ws_state_fresh_false_when_never_updated(
        self, sut: CyclonextSystem
    ) -> None:
        assert sut._ws_state_fresh() is False

    def test_ws_state_fresh_true_when_recent(
        self, sut: CyclonextSystem
    ) -> None:
        sut._ws_connected = True
        sut._ws_last_update = time.time()
        assert sut._ws_state_fresh() is True

    def test_ws_state_fresh_false_when_stale(
        self, sut: CyclonextSystem
    ) -> None:
        sut._ws_connected = True
        sut._ws_last_update = time.time() - 10_000
        assert sut._ws_state_fresh() is False

    def test_ws_state_fresh_false_when_disconnected(
        self, sut: CyclonextSystem
    ) -> None:
        # Recent state but the socket dropped → must poll REST again.
        sut._ws_connected = False
        sut._ws_last_update = time.time()
        assert sut._ws_state_fresh() is False

    async def test_refresh_polls_rest_when_no_ws_state(
        self, sut: CyclonextSystem
    ) -> None:
        with (
            patch.object(sut, "send_shadow_request", new=AsyncMock()) as m,
            patch.object(sut, "_parse_shadow_response"),
        ):
            await sut._refresh()
        m.assert_awaited_once()

    async def test_refresh_skips_rest_when_ws_fresh(
        self, sut: CyclonextSystem
    ) -> None:
        sut._ws_connected = True
        sut._ws_last_update = time.time()
        with patch.object(sut, "send_shadow_request", new=AsyncMock()) as m:
            await sut._refresh()
        m.assert_not_awaited()

    async def test_refresh_polls_rest_when_ws_stale(
        self, sut: CyclonextSystem
    ) -> None:
        sut._ws_connected = True
        sut._ws_last_update = time.time() - 10_000
        with (
            patch.object(sut, "send_shadow_request", new=AsyncMock()) as m,
            patch.object(sut, "_parse_shadow_response"),
        ):
            await sut._refresh()
        m.assert_awaited_once()

    def test_subscribe_frame_shape(self, sut: CyclonextSystem) -> None:
        sut.aqualink.user_id = "12345"
        frame = sut._ws_subscribe_frame()
        assert frame["action"] == "subscribe"
        assert frame["namespace"] == "authorization"
        assert frame["service"] == "Authorization"
        assert frame["payload"] == {"userId": 12345}
        assert frame["target"] == sut.serial

    def test_apply_auth_full_state(self, sut: CyclonextSystem) -> None:
        assert sut._apply_ws_frame(_AUTH_FULL_FRAME) is True
        assert sut._robot_state["mode"] == 0
        assert sut._robot_state["cycle"] == 1
        assert "running" in sut.devices
        assert "robot" in sut.devices

    def test_apply_reported_delta_merges(self, sut: CyclonextSystem) -> None:
        sut._apply_ws_frame(_AUTH_FULL_FRAME)
        assert sut._apply_ws_frame(_DELTA_FRAME) is True
        assert sut._robot_state["mode"] == 1  # delta wins
        assert sut._robot_state["cycle"] == 1  # retained from full state
        assert sut.devices["mode"].data["state"] == 1
        assert cast(AqualinkBinarySensor, sut.devices["running"]).is_on is True

    def test_apply_ignores_desired_echo(self, sut: CyclonextSystem) -> None:
        sut._apply_ws_frame(_AUTH_FULL_FRAME)
        assert sut._apply_ws_frame(_ECHO_FRAME) is False
        assert sut._robot_state["mode"] == 0  # unchanged

    def test_apply_ignores_unknown_frame(self, sut: CyclonextSystem) -> None:
        assert sut._apply_ws_frame({"service": "Keepalive"}) is False

    async def test_receive_loop_subscribes_and_applies(
        self, sut: CyclonextSystem
    ) -> None:
        sut.aqualink.user_id = "12345"
        ws = AsyncMock()
        ws.receive_text = AsyncMock(
            side_effect=[
                json.dumps(_AUTH_FULL_FRAME),
                "Ping",  # non-JSON keepalive — skipped
                json.dumps(_DELTA_FRAME),
                ConnectionError("closed"),
            ]
        )
        cm = MagicMock()
        cm.__aenter__ = AsyncMock(return_value=ws)
        cm.__aexit__ = AsyncMock(return_value=None)
        with (
            patch.object(sut.aqualink, "ws_connect", return_value=cm),
            pytest.raises(ConnectionError),
        ):
            await sut._ws_receive_loop()

        sent = json.loads(ws.send_text.await_args.args[0])
        assert sent["action"] == "subscribe"
        assert sut._robot_state["mode"] == 1  # delta applied after full state
        assert sut._ws_last_update is not None
        assert sut._ws_connected is False  # finally marks the socket down

    async def test_start_ws_subscription_noop_when_disabled(
        self, sut: CyclonextSystem
    ) -> None:
        sut._ws_enabled = False
        await sut.start_ws_subscription()
        assert sut._ws_task is None

    async def test_stop_ws_subscription_safe_without_task(
        self, sut: CyclonextSystem
    ) -> None:
        await sut.stop_ws_subscription()
        assert sut._ws_task is None
