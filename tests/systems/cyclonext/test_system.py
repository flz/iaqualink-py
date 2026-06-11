"""Tests for cyclonext system."""

from __future__ import annotations

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

from ...base_test_system import TestBaseSystem
from ...conftest import load_fixture

CYCLONEXT_DATA = {
    "name": "Pool Robot",
    "serial_number": "SN42",
    "device_type": "cyclonext",
    "id": 1,
}


class TestCyclonextSystem(TestBaseSystem):
    def setUp(self) -> None:
        super().setUp()
        self.sut = AqualinkSystem.from_data(self.client, data=CYCLONEXT_DATA)
        self.sut_class = CyclonextSystem

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
        respx.get(f"{CYCLONEXT_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(
                200, json=load_fixture("cyclonext", "shadow_get")
            )
        )
        await self.sut.refresh()
        assert self.sut.status is SystemStatus.ONLINE
        assert "mode" in self.sut.devices
        assert self.sut.devices["mode"].data["state"] == 1
        assert "error_code" in self.sut.devices
        assert self.sut.devices["error_code"].data["state"] == 0
        assert "ebox_sn" in self.sut.devices
        assert self.sut.devices["ebox_sn"].data["state"] == "EBOX42"
        assert "control_box_vr" in self.sut.devices
        assert self.sut.devices["control_box_vr"].data["state"] == "cb-2.1"
        assert "running" in self.sut.devices
        assert self.sut.devices["running"].data["state"] == 1
        assert "model_number" in self.sut.devices
        assert "time_remaining_sec" in self.sut.devices

        robot = self.sut.devices["robot"]
        assert isinstance(robot, CyclonextRobot)
        # fixture mode == 1 -> cleaning.
        assert robot.activity is AqualinkRobotActivity.CLEANING

    @respx.mock
    async def test_refresh_missing_robot_sets_offline(self) -> None:
        # robot list contains only null entries → offline.
        respx.get(f"{CYCLONEXT_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(
                200,
                json={"state": {"reported": {"equipment": {"robot": [None]}}}},
            )
        )
        await self.sut.refresh()
        assert self.sut.status == SystemStatus.OFFLINE

    async def test_refresh_throttled_sets_unknown_and_propagates(self) -> None:
        with patch.object(self.sut, "send_shadow_request") as mock_req:
            mock_req.side_effect = AqualinkServiceThrottledException
            with pytest.raises(AqualinkServiceThrottledException):
                await self.sut.refresh()
        assert self.sut.status == SystemStatus.UNKNOWN

    async def test_start_cleaning_dispatches_mode_start(self) -> None:
        from iaqualink.systems.cyclonext import system as sys_mod

        with (
            patch.object(sys_mod, "send_set_mode", new=AsyncMock()) as m_mode,
            patch.object(sys_mod, "send_set_cycle", new=AsyncMock()) as m_cycle,
        ):
            await self.sut.start_cleaning()
            m_mode.assert_awaited_once_with(self.client, "SN42", mode=1)
            m_cycle.assert_not_awaited()

    async def test_start_cleaning_with_cycle_sets_cycle_first(self) -> None:
        from iaqualink.systems.cyclonext import system as sys_mod

        with (
            patch.object(sys_mod, "send_set_mode", new=AsyncMock()) as m_mode,
            patch.object(sys_mod, "send_set_cycle", new=AsyncMock()) as m_cycle,
        ):
            await self.sut.start_cleaning(cycle=3)
            m_cycle.assert_awaited_once_with(self.client, "SN42", cycle=3)
            m_mode.assert_awaited_once_with(self.client, "SN42", mode=1)

    async def test_stop_cleaning_dispatches_mode_stop(self) -> None:
        from iaqualink.systems.cyclonext import system as sys_mod

        with patch.object(sys_mod, "send_set_mode", new=AsyncMock()) as m:
            await self.sut.stop_cleaning()
            m.assert_awaited_once_with(self.client, "SN42", mode=0)

    async def test_pause_cleaning_dispatches_mode_pause(self) -> None:
        from iaqualink.systems.cyclonext import system as sys_mod

        with patch.object(sys_mod, "send_set_mode", new=AsyncMock()) as m:
            await self.sut.pause_cleaning()
            m.assert_awaited_once_with(self.client, "SN42", mode=2)

    async def test_set_runtime_extension_dispatches_stepper(self) -> None:
        from iaqualink.systems.cyclonext import system as sys_mod

        with patch.object(sys_mod, "send_set_stepper", new=AsyncMock()) as m:
            await self.sut.set_runtime_extension(30)
            m.assert_awaited_once_with(self.client, "SN42", minutes=30)

    async def test_set_runtime_extension_negative_raises(self) -> None:
        with self.assertRaises(AqualinkInvalidParameterException):
            await self.sut.set_runtime_extension(-15)

    async def test_set_runtime_extension_non_multiple_raises(self) -> None:
        with self.assertRaises(AqualinkInvalidParameterException):
            await self.sut.set_runtime_extension(10)

    async def test_adjust_runtime_clamps_at_zero(self) -> None:
        # Seed internal cache so adjust_runtime has a baseline.
        self.sut._robot_state = {"stepper": 0}
        from iaqualink.systems.cyclonext import system as sys_mod

        with patch.object(sys_mod, "send_set_stepper", new=AsyncMock()) as m:
            new_value = await self.sut.adjust_runtime(-30)
            assert new_value == 0
            m.assert_awaited_once_with(self.client, "SN42", minutes=0)

    async def test_adjust_runtime_non_multiple_raises(self) -> None:
        with self.assertRaises(AqualinkInvalidParameterException):
            await self.sut.adjust_runtime(10)

    async def test_remote_forward_dispatches_mode_remote_direction_forward(
        self,
    ) -> None:
        from iaqualink.systems.cyclonext import system as sys_mod

        with patch.object(
            sys_mod, "send_set_remote_state", new=AsyncMock()
        ) as m:
            await self.sut.remote_forward()
            m.assert_awaited_once_with(self.client, "SN42", mode=2, direction=1)

    async def test_remote_stop_dispatches_mode_remote_direction_stop(
        self,
    ) -> None:
        from iaqualink.systems.cyclonext import system as sys_mod

        with patch.object(
            sys_mod, "send_set_remote_state", new=AsyncMock()
        ) as m:
            await self.sut.remote_stop()
            m.assert_awaited_once_with(self.client, "SN42", mode=2, direction=0)

    async def test_lift_eject_dispatches_mode_lift_direction_eject(
        self,
    ) -> None:
        from iaqualink.systems.cyclonext import system as sys_mod

        with patch.object(
            sys_mod, "send_set_remote_state", new=AsyncMock()
        ) as m:
            await self.sut.lift_eject()
            m.assert_awaited_once_with(self.client, "SN42", mode=3, direction=5)
