"""Tests for Vortrax system."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import respx

from iaqualink.systems.vortrax.system import VortraxSystem
from iaqualink.systems.vr.system import VR_DEVICES_URL
from tests.base import TestBase

VORTRAX_DATA = {
    "name": "Pool Robot",
    "serial_number": "SN42",
    "device_type": "vortrax",
    "id": 1,
}

SHADOW_RESPONSE = {
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
            "eboxData": {"completeCleanerPn": "VTX-PN-42"},
        },
    },
}


class TestVortraxSystem(TestBase):
    async def asyncSetUp(self) -> None:
        await super().asyncSetUp()
        self.system = VortraxSystem(self.client, VORTRAX_DATA)

    def test_name(self) -> None:
        assert VortraxSystem.NAME == "vortrax"

    def test_namespace(self) -> None:
        assert VortraxSystem.namespace == "vortrax"

    @respx.mock
    async def test_parse_shadow_surfaces_product_number(self) -> None:
        respx.get(f"{VR_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(200, json=SHADOW_RESPONSE)
        )
        await self.system.refresh()
        assert "product_number" in self.system.devices
        assert (
            self.system.devices["product_number"].data["state"] == "VTX-PN-42"
        )

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
        await self.system.refresh()
        assert "product_number" not in self.system.devices

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
        await self.system.refresh()
        assert "product_number" not in self.system.devices

    @respx.mock
    async def test_inherited_vr_devices_present(self) -> None:
        respx.get(f"{VR_DEVICES_URL}/SN42/shadow").mock(
            return_value=httpx.Response(200, json=SHADOW_RESPONSE)
        )
        await self.system.refresh()
        # VR base devices still emitted
        assert "state" in self.system.devices
        assert "running" in self.system.devices
        assert "returning" in self.system.devices
        assert "model_number" in self.system.devices

    async def test_start_cleaning_uses_vortrax_namespace(self) -> None:
        from iaqualink.systems.vr import system as vr_sys_mod

        with patch.object(vr_sys_mod, "send_set_state", new=AsyncMock()) as m:
            await self.system.start_cleaning()
            m.assert_awaited_once_with(
                self.client, "SN42", 1, namespace="vortrax"
            )
