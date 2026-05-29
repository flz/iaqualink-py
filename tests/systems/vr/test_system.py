"""Tests for VR system."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from iaqualink.exception import (
    AqualinkInvalidParameterException,
    AqualinkServiceThrottledException,
)
from iaqualink.system import SystemStatus
from iaqualink.systems.vr.system import (
    VR_DEVICES_URL,
    VrSystem,
)
from tests.base import TestBase

VR_DATA = {
    "name": "Pool Robot",
    "serial_number": "SN42",
    "device_type": "vr",
    "id": 1,
}

SHADOW_RESPONSE = {
    "state": {
        "reported": {
            "equipment": {
                "robot": {
                    "state": 1,
                    "errorState": 0,
                    "prCyc": 1,
                    "stepper": 30,
                    "cycleStartTime": 1000,
                    "durations": {
                        "wallTim": 60,
                        "floorTim": 90,
                        "smartTim": 120,
                        "floorWallsTim": 150,
                    },
                    "sensors": {"sns_1": {"val": 25}},
                    "sn": "SN42",
                    "vr": "1.0.0",
                },
            },
        },
    },
}


class TestVrSystem(TestBase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.system = VrSystem(self.client, VR_DATA)

    @respx.mock
    async def test_refresh_parses_shadow_and_sets_online(self) -> None:
        respx.get(f"{VR_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(200, json=SHADOW_RESPONSE)
        )
        await self.system.refresh()
        assert self.system.status == SystemStatus.ONLINE
        # Scalar attributes surfaced
        assert "state" in self.system.devices
        assert self.system.devices["state"].data["state"] == 1
        # Binary sensors
        assert "running" in self.system.devices
        assert self.system.devices["running"].data["state"] == 1
        assert "returning" in self.system.devices
        assert self.system.devices["returning"].data["state"] == 0
        # Temperature from sns_1.val
        assert "temperature" in self.system.devices
        assert self.system.devices["temperature"].data["state"] == 25
        # Model number from data["id"]
        assert "model_number" in self.system.devices
        assert self.system.devices["model_number"].data["state"] == 1
        # Derived time_remaining_sec present
        assert "time_remaining_sec" in self.system.devices
        # HA-vacuum-style robot device (T31).
        from iaqualink.device import AqualinkRobot, AqualinkRobotActivity
        from iaqualink.systems.vr.device import VrRobot

        robot = self.system.devices["robot"]
        assert isinstance(robot, VrRobot)
        assert isinstance(robot, AqualinkRobot)
        # SHADOW_RESPONSE state == 1 -> cleaning.
        assert robot.activity is AqualinkRobotActivity.CLEANING
        # Error scalar surfaced as snake_case error_state -> VrErrorSensor.
        from iaqualink.systems.vr.device import VrErrorSensor

        assert "errorState" not in self.system.devices
        assert isinstance(self.system.devices["error_state"], VrErrorSensor)

    @respx.mock
    async def test_refresh_missing_robot_sets_offline(self) -> None:
        respx.get(f"{VR_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(
                200,
                json={"state": {"reported": {"equipment": {}}}},
            )
        )
        await self.system.refresh()
        assert self.system.status == SystemStatus.OFFLINE

    @respx.mock
    async def test_refresh_robot_not_dict_sets_offline(self) -> None:
        # robot as list (wrong shape) → OFFLINE
        respx.get(f"{VR_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(
                200,
                json={"state": {"reported": {"equipment": {"robot": []}}}},
            )
        )
        await self.system.refresh()
        assert self.system.status == SystemStatus.OFFLINE

    async def test_refresh_throttled_propagates_and_status_unknown(
        self,
    ) -> None:
        with patch.object(
            self.system,
            "send_shadow_request",
            new=AsyncMock(side_effect=AqualinkServiceThrottledException),
        ):
            with pytest.raises(AqualinkServiceThrottledException):
                await self.system.refresh()
        assert self.system.status == SystemStatus.UNKNOWN

    # --- write commands ---------------------------------------------------

    async def test_start_cleaning_dispatches_state_cleaning(self) -> None:
        from iaqualink.systems.vr import system as sys_mod

        with patch.object(sys_mod, "send_set_state", new=AsyncMock()) as m:
            await self.system.start_cleaning()
            m.assert_awaited_once_with(self.client, "SN42", 1, namespace="vr")

    async def test_start_cleaning_with_cycle_sets_cycle_first(self) -> None:
        from iaqualink.systems.vr import system as sys_mod

        with (
            patch.object(sys_mod, "send_set_state", new=AsyncMock()) as m_state,
            patch.object(sys_mod, "send_set_cycle", new=AsyncMock()) as m_cycle,
        ):
            await self.system.start_cleaning(cycle=2)
            m_cycle.assert_awaited_once_with(
                self.client, "SN42", 2, namespace="vr"
            )
            m_state.assert_awaited_once_with(
                self.client, "SN42", 1, namespace="vr"
            )

    async def test_stop_cleaning_dispatches_state_stopped(self) -> None:
        from iaqualink.systems.vr import system as sys_mod

        with patch.object(sys_mod, "send_set_state", new=AsyncMock()) as m:
            await self.system.stop_cleaning()
            m.assert_awaited_once_with(self.client, "SN42", 0, namespace="vr")

    async def test_pause_cleaning_dispatches_state_paused(self) -> None:
        from iaqualink.systems.vr import system as sys_mod

        with patch.object(sys_mod, "send_set_state", new=AsyncMock()) as m:
            await self.system.pause_cleaning()
            m.assert_awaited_once_with(self.client, "SN42", 2, namespace="vr")

    async def test_return_to_base_dispatches_state_returning(self) -> None:
        from iaqualink.systems.vr import system as sys_mod

        with patch.object(sys_mod, "send_set_state", new=AsyncMock()) as m:
            await self.system.return_to_base()
            m.assert_awaited_once_with(self.client, "SN42", 3, namespace="vr")

    async def test_set_cycle_invalid_raises(self) -> None:
        with pytest.raises(AqualinkInvalidParameterException):
            await self.system.set_cycle(99)

    async def test_set_runtime_extension_dispatches_stepper(self) -> None:
        from iaqualink.systems.vr import system as sys_mod

        with patch.object(sys_mod, "send_set_stepper", new=AsyncMock()) as m:
            await self.system.set_runtime_extension(30)
            m.assert_awaited_once_with(self.client, "SN42", 30, namespace="vr")

    async def test_set_runtime_extension_negative_raises(self) -> None:
        with pytest.raises(AqualinkInvalidParameterException):
            await self.system.set_runtime_extension(-15)

    async def test_set_runtime_extension_non_multiple_raises(self) -> None:
        with pytest.raises(AqualinkInvalidParameterException):
            await self.system.set_runtime_extension(10)

    async def test_adjust_runtime_clamps_at_zero(self) -> None:
        self.system._robot_state = {"stepper": 0}
        from iaqualink.systems.vr import system as sys_mod

        with patch.object(sys_mod, "send_set_stepper", new=AsyncMock()) as m:
            new_value = await self.system.adjust_runtime(-30)
            assert new_value == 0
            m.assert_awaited_once_with(self.client, "SN42", 0, namespace="vr")

    async def test_adjust_runtime_non_multiple_raises(self) -> None:
        with pytest.raises(AqualinkInvalidParameterException):
            await self.system.adjust_runtime(10)

    # --- remote control ---------------------------------------------------

    async def test_remote_forward_first_call_pauses_then_sends(self) -> None:
        from iaqualink.systems.vr import system as sys_mod

        with (
            patch.object(sys_mod, "send_set_state", new=AsyncMock()) as m_state,
            patch.object(
                sys_mod, "send_remote_steering", new=AsyncMock()
            ) as m_rmt,
        ):
            await self.system.remote_forward()
            # First call: state=PAUSED emitted, then rmt_ctrl=FORWARD
            m_state.assert_awaited_once_with(
                self.client, "SN42", 2, namespace="vr"
            )
            m_rmt.assert_awaited_once_with(
                self.client, "SN42", 1, namespace="vr"
            )

    async def test_remote_forward_second_call_no_extra_pause(self) -> None:
        from iaqualink.systems.vr import system as sys_mod

        with (
            patch.object(sys_mod, "send_set_state", new=AsyncMock()) as m_state,
            patch.object(
                sys_mod, "send_remote_steering", new=AsyncMock()
            ) as m_rmt,
        ):
            await self.system.remote_forward()
            await self.system.remote_forward()
            # state=PAUSED emitted exactly once (on first remote call only)
            m_state.assert_awaited_once_with(
                self.client, "SN42", 2, namespace="vr"
            )
            assert m_rmt.await_count == 2

    async def test_remote_stop_sends_rmt_ctrl_stop_then_state_stopped(
        self,
    ) -> None:
        from iaqualink.systems.vr import system as sys_mod

        # Put system into remote-active state first
        self.system._remote_control_active = True

        with (
            patch.object(sys_mod, "send_set_state", new=AsyncMock()) as m_state,
            patch.object(
                sys_mod, "send_remote_steering", new=AsyncMock()
            ) as m_rmt,
        ):
            await self.system.remote_stop()
            m_rmt.assert_awaited_once_with(
                self.client, "SN42", 0, namespace="vr"
            )
            # _exit_remote_mode → state=STOPPED
            m_state.assert_awaited_once_with(
                self.client, "SN42", 0, namespace="vr"
            )
        # Flag cleared
        assert self.system._remote_control_active is False
