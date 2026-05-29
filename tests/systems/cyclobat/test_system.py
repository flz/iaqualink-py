"""Tests for cyclobat system."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from iaqualink.exception import AqualinkServiceThrottledException
from iaqualink.system import SystemStatus
from iaqualink.systems.cyclobat.system import (
    CYCLOBAT_DEVICES_URL,
    CyclobatSystem,
)
from tests.base import TestBase

CYCLOBAT_DATA = {
    "name": "Pool Robot",
    "serial_number": "SN42",
    "device_type": "cyclobat",
    "id": "CV3000",
}

SHADOW_RESPONSE = {
    "state": {
        "reported": {
            "equipment": {
                "robot": {
                    "vr": "1.2.3",
                    "sn": "SN42",
                    "main": {
                        "state": 1,
                        "ctrl": 1,
                        "mode": 0,
                        "error": 0,
                        "cycleStartTime": 1000,
                    },
                    "battery": {
                        "vr": "v1",
                        "state": 2,
                        "userChargePerc": 87,
                        "userChargeState": 1,
                        "cycles": 12,
                        "warning": {"code": 0},
                    },
                    "stats": {
                        "totRunTime": 1234,
                        "diagnostic": 0,
                        "tmp": 25,
                        "lastError": {"code": 0, "cycleNb": 5},
                    },
                    "lastCycle": {
                        "cycleNb": 5,
                        "duration": 90,
                        "mode": 1,
                        "endCycleType": 0,
                        "errorCode": 0,
                    },
                    "cycles": {
                        "floorTim": {"duration": 90},
                        "floorWallsTim": {"duration": 120},
                        "smartTim": {"duration": 105},
                        "waterlineTim": {"duration": 60},
                        "firstSmartDone": True,
                        "liftPatternTim": 5,
                    },
                },
            },
        },
    },
}


class TestCyclobatSystem(TestBase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.system = CyclobatSystem(self.client, CYCLOBAT_DATA)

    @respx.mock
    async def test_refresh_parses_shadow_and_sets_online(self) -> None:
        respx.get(f"{CYCLOBAT_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(200, json=SHADOW_RESPONSE)
        )
        await self.system.refresh()
        assert self.system.status == SystemStatus.ONLINE
        assert "battery_percentage" in self.system.devices
        assert self.system.devices["battery_percentage"].data["state"] == 87
        assert "running" in self.system.devices
        # Robot device exposed as an HA-vacuum-style AqualinkRobot.
        from iaqualink.device import AqualinkRobot, AqualinkRobotActivity
        from iaqualink.systems.cyclobat.device import CyclobatRobot

        robot = self.system.devices["robot"]
        assert isinstance(robot, CyclobatRobot)
        assert isinstance(robot, AqualinkRobot)
        # SHADOW_RESPONSE main.state == 1 -> cleaning.
        assert robot.activity is AqualinkRobotActivity.CLEANING
        assert self.system.devices["running"].data["state"] == 1
        assert "model_number" in self.system.devices

    @respx.mock
    async def test_v23_total_runtime_is_minutes_not_hours(self) -> None:
        # V23: stats.totRunTime is MINUTES; the key must be unit-neutral,
        # not `total_hours` (which implies a different unit). backprop §B2.
        respx.get(f"{CYCLOBAT_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(200, json=SHADOW_RESPONSE)
        )
        await self.system.refresh()
        assert "total_runtime" in self.system.devices
        assert "total_hours" not in self.system.devices
        runtime = self.system.devices["total_runtime"]
        assert runtime.unit_of_measurement == "min"
        assert runtime.device_class == "duration"
        assert runtime.state_class == "total_increasing"
        assert runtime.native_value == 1234

    @respx.mock
    async def test_refresh_missing_robot_sets_offline(self) -> None:
        respx.get(f"{CYCLOBAT_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(200, json={"state": {"reported": {}}})
        )
        await self.system.refresh()
        assert self.system.status == SystemStatus.OFFLINE

    async def test_refresh_throttled_sets_unknown_and_propagates(self) -> None:
        with patch.object(self.system, "send_shadow_request") as mock_req:
            mock_req.side_effect = AqualinkServiceThrottledException
            with pytest.raises(AqualinkServiceThrottledException):
                await self.system.refresh()
        assert self.system.status == SystemStatus.UNKNOWN

    async def test_start_cleaning_calls_send_set_ctrl(self) -> None:
        from iaqualink.systems.cyclobat import system as sys_mod

        with patch.object(sys_mod, "send_set_ctrl", new=AsyncMock()) as m:
            await self.system.start_cleaning()
            m.assert_awaited_once_with(self.client, "SN42", 1)

    async def test_stop_cleaning_calls_send_set_ctrl(self) -> None:
        from iaqualink.systems.cyclobat import system as sys_mod

        with patch.object(sys_mod, "send_set_ctrl", new=AsyncMock()) as m:
            await self.system.stop_cleaning()
            m.assert_awaited_once_with(self.client, "SN42", 0)

    async def test_return_to_base_calls_send_set_ctrl(self) -> None:
        from iaqualink.systems.cyclobat import system as sys_mod

        with patch.object(sys_mod, "send_set_ctrl", new=AsyncMock()) as m:
            await self.system.return_to_base()
            m.assert_awaited_once_with(self.client, "SN42", 3)
