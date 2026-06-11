from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from iaqualink.enums import AqualinkRobotActivity
from iaqualink.exception import AqualinkServiceThrottledException
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.cyclobat.device import CyclobatRobot
from iaqualink.systems.cyclobat.system import (
    CYCLOBAT_DEVICES_URL,
    CyclobatSystem,
)

from ...base_test_system import TestBaseSystem
from ...conftest import load_fixture

CYCLOBAT_DATA = {
    "id": "CV3000",
    "serial_number": "SN42",
    "device_type": "cyclobat",
    "name": "Pool Robot",
}


class TestCyclobatSystem(TestBaseSystem):
    def setUp(self) -> None:
        super().setUp()
        self.sut = AqualinkSystem.from_data(self.client, data=CYCLOBAT_DATA)
        self.sut_class = CyclobatSystem

    def _set_online(self, _response: object) -> None:
        self.sut.status = SystemStatus.ONLINE

    async def test_refresh_success(self) -> None:
        # drive status via parse hook; inherited test asserts ONLINE.
        with patch.object(
            self.sut, "_parse_shadow_response", side_effect=self._set_online
        ):
            await super().test_refresh_success()

    @respx.mock
    async def test_refresh_parses_shadow_and_sets_online(self) -> None:
        respx.get(f"{CYCLOBAT_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(
                200, json=load_fixture("cyclobat", "shadow_get")
            )
        )
        await self.sut.refresh()
        assert self.sut.status is SystemStatus.ONLINE
        assert "battery_percentage" in self.sut.devices
        assert self.sut.devices["battery_percentage"].value == 87
        assert "running" in self.sut.devices

        robot = self.sut.devices["robot"]
        assert isinstance(robot, CyclobatRobot)
        # fixture main.state == 1 -> cleaning.
        assert robot.activity is AqualinkRobotActivity.CLEANING
        assert self.sut.devices["running"].data["state"] == 1
        assert "model_number" in self.sut.devices

    @respx.mock
    async def test_total_runtime_is_minutes_not_hours(self) -> None:
        # V23: stats.totRunTime is MINUTES; the key must be unit-neutral, not
        # `total_hours` (which implies a different unit). backprop §B2.
        respx.get(f"{CYCLOBAT_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(
                200, json=load_fixture("cyclobat", "shadow_get")
            )
        )
        await self.sut.refresh()
        assert "total_runtime" in self.sut.devices
        assert "total_hours" not in self.sut.devices
        runtime = self.sut.devices["total_runtime"]
        assert runtime.unit_of_measurement == "min"
        assert runtime.device_class is None
        assert runtime.state_class == "total_increasing"
        assert runtime.value == 1234

    @respx.mock
    async def test_refresh_missing_robot_sets_offline(self) -> None:
        respx.get(f"{CYCLOBAT_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(200, json={"state": {"reported": {}}})
        )
        await self.sut.refresh()
        assert self.sut.status is SystemStatus.OFFLINE

    async def test_refresh_throttled_sets_unknown_and_propagates(self) -> None:
        with patch.object(self.sut, "send_shadow_request") as mock_req:
            mock_req.side_effect = AqualinkServiceThrottledException
            with pytest.raises(AqualinkServiceThrottledException):
                await self.sut.refresh()
        assert self.sut.status is SystemStatus.UNKNOWN

    async def test_start_cleaning_calls_send_set_ctrl(self) -> None:
        from iaqualink.systems.cyclobat import system as sys_mod

        with patch.object(sys_mod, "send_set_ctrl", new=AsyncMock()) as m:
            await self.sut.start_cleaning()
            m.assert_awaited_once_with(self.client, "SN42", 1)

    async def test_stop_cleaning_calls_send_set_ctrl(self) -> None:
        from iaqualink.systems.cyclobat import system as sys_mod

        with patch.object(sys_mod, "send_set_ctrl", new=AsyncMock()) as m:
            await self.sut.stop_cleaning()
            m.assert_awaited_once_with(self.client, "SN42", 0)

    async def test_return_to_base_calls_send_set_ctrl(self) -> None:
        from iaqualink.systems.cyclobat import system as sys_mod

        with patch.object(sys_mod, "send_set_ctrl", new=AsyncMock()) as m:
            await self.sut.return_to_base()
            m.assert_awaited_once_with(self.client, "SN42", 3)
