"""Tests for Vortrax system."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import respx

from iaqualink.enums import AqualinkRobotActivity
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.vortrax.system import VortraxSystem
from iaqualink.systems.vr.device import VrRobot
from iaqualink.systems.vr.system import VR_DEVICES_URL

from ...base_test_system import TestBaseSystem
from ...conftest import load_fixture

VORTRAX_DATA = {
    "name": "Pool Robot",
    "serial_number": "SN42",
    "device_type": "vortrax",
    "id": 1,
}


class TestVortraxSystem(TestBaseSystem):
    def setUp(self) -> None:
        super().setUp()
        self.sut = AqualinkSystem.from_data(self.client, data=VORTRAX_DATA)
        self.sut_class = VortraxSystem

    def _set_online(self, _response: object) -> None:
        self.sut.status = SystemStatus.ONLINE

    async def test_refresh_success(self) -> None:
        # drive status via parse hook; inherited test asserts ONLINE.
        with patch.object(
            self.sut, "_parse_shadow_response", side_effect=self._set_online
        ):
            await super().test_refresh_success()

    def test_name(self) -> None:
        assert VortraxSystem.NAME == "vortrax"

    def test_namespace(self) -> None:
        assert VortraxSystem.namespace == "vortrax"

    @respx.mock
    async def test_parse_shadow_surfaces_product_number(self) -> None:
        respx.get(f"{VR_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(
                200, json=load_fixture("vortrax", "shadow_get")
            )
        )
        await self.sut.refresh()
        assert "product_number" in self.sut.devices
        assert self.sut.devices["product_number"].data["state"] == "VTX-PN-42"

    @respx.mock
    async def test_parse_shadow_no_ebox_no_product_number(self) -> None:
        shadow_no_ebox = {
            "state": {
                "reported": {
                    "equipment": {
                        "robot": {
                            "state": 1,
                            "prCyc": 1,
                            "stepper": 0,
                            "sn": "SN42",
                            "vr": "1.0.0",
                        },
                    },
                },
            },
        }
        respx.get(f"{VR_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(200, json=shadow_no_ebox)
        )
        await self.sut.refresh()
        assert "product_number" not in self.sut.devices

    @respx.mock
    async def test_parse_shadow_ebox_missing_pn_no_product_number(self) -> None:
        shadow_no_pn = {
            "state": {
                "reported": {
                    "equipment": {
                        "robot": {
                            "state": 1,
                            "prCyc": 1,
                            "stepper": 0,
                            "sn": "SN42",
                            "vr": "1.0.0",
                        },
                    },
                    "eboxData": {},
                },
            },
        }
        respx.get(f"{VR_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(200, json=shadow_no_pn)
        )
        await self.sut.refresh()
        assert "product_number" not in self.sut.devices

    @respx.mock
    async def test_inherited_vr_devices_present(self) -> None:
        respx.get(f"{VR_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(
                200, json=load_fixture("vortrax", "shadow_get")
            )
        )
        await self.sut.refresh()
        # VR base devices still emitted
        assert "state" in self.sut.devices
        assert "running" in self.sut.devices
        assert "returning" in self.sut.devices
        assert "model_number" in self.sut.devices

    @respx.mock
    async def test_inherited_robot_device_is_vrrobot(self) -> None:
        # VortraxSystem reuses VrSystem's parser, so it inherits the VrRobot
        # HA-vacuum device with no vortrax-specific code (T31).
        respx.get(f"{VR_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(
                200, json=load_fixture("vortrax", "shadow_get")
            )
        )
        await self.sut.refresh()
        robot = self.sut.devices["robot"]
        assert isinstance(robot, VrRobot)
        assert robot.activity is AqualinkRobotActivity.CLEANING

    @respx.mock
    async def test_product_number_is_diagnostic(self) -> None:
        respx.get(f"{VR_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(
                200, json=load_fixture("vortrax", "shadow_get")
            )
        )
        await self.sut.refresh()
        assert (
            self.sut.devices["product_number"].entity_category == "diagnostic"
        )

    async def test_start_cleaning_uses_vortrax_namespace(self) -> None:
        from iaqualink.systems.vr import system as vr_sys_mod

        with patch.object(vr_sys_mod, "send_set_state", new=AsyncMock()) as m:
            await self.sut.start_cleaning()
            m.assert_awaited_once_with(
                self.client, "SN42", 1, namespace="vortrax"
            )
