"""Vortrax-specific system tests.

Generic AqualinkSystem contract is covered by tests/conformance/test_system.py
via the vortrax system_fixture; this module keeps only vortrax-specific
behaviour: registration, namespace, subclass reuse of vr devices, and the
extra product-number sensor parsed from eboxData.
"""

from __future__ import annotations

from typing import cast
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from iaqualink.enums import AqualinkRobotActivity
from iaqualink.system import AqualinkSystem
from iaqualink.systems.vortrax.system import VortraxSystem
from iaqualink.systems.vr.device import VrRobot
from iaqualink.systems.vr.system import VR_DEVICES_URL

from ...conftest import load_fixture

VORTRAX_DATA = {
    "name": "Pool Robot",
    "serial_number": "SN42",
    "device_type": "vortrax",
    "id": 1,
}


@pytest.fixture
def sut(client) -> VortraxSystem:
    return cast(
        VortraxSystem, AqualinkSystem.from_data(client, data=VORTRAX_DATA)
    )


def _mock_shadow(payload: dict) -> None:
    respx.get(f"{VR_DEVICES_URL}/SN42/shadow").mock(
        return_value=httpx.Response(200, json=payload)
    )


def test_registered() -> None:
    assert "vortrax" in AqualinkSystem.subclasses


def test_name() -> None:
    assert VortraxSystem.NAME == "vortrax"


def test_namespace() -> None:
    assert VortraxSystem.namespace == "vortrax"


@respx.mock
async def test_parse_shadow_surfaces_product_number(
    sut: VortraxSystem,
) -> None:
    _mock_shadow(load_fixture("vortrax", "shadow_get"))
    await sut.refresh()
    assert "product_number" in sut.devices
    assert sut.devices["product_number"].data["state"] == "VTX-PN-42"


@respx.mock
async def test_product_number_updates_on_second_refresh(
    sut: VortraxSystem,
) -> None:
    _mock_shadow(load_fixture("vortrax", "shadow_get"))
    await sut.refresh()
    await sut.refresh()  # second pass updates the existing product_number
    assert sut.devices["product_number"].data["state"] == "VTX-PN-42"


@respx.mock
async def test_parse_shadow_no_ebox_no_product_number(
    sut: VortraxSystem,
) -> None:
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
    _mock_shadow(shadow_no_ebox)
    await sut.refresh()
    assert "product_number" not in sut.devices


@respx.mock
async def test_parse_shadow_ebox_missing_pn_no_product_number(
    sut: VortraxSystem,
) -> None:
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
    _mock_shadow(shadow_no_pn)
    await sut.refresh()
    assert "product_number" not in sut.devices


@respx.mock
async def test_inherited_vr_devices_present(sut: VortraxSystem) -> None:
    _mock_shadow(load_fixture("vortrax", "shadow_get"))
    await sut.refresh()
    # VR base devices still emitted.
    assert "state" in sut.devices
    assert "running" in sut.devices
    assert "returning" in sut.devices
    assert "model_number" in sut.devices


@respx.mock
async def test_inherited_robot_device_is_vrrobot(sut: VortraxSystem) -> None:
    # VortraxSystem reuses VrSystem's parser, so it inherits the VrRobot
    # HA-vacuum device with no vortrax-specific code (T31).
    _mock_shadow(load_fixture("vortrax", "shadow_get"))
    await sut.refresh()
    robot = sut.devices["robot"]
    assert isinstance(robot, VrRobot)
    assert robot.activity is AqualinkRobotActivity.CLEANING


@respx.mock
async def test_product_number_is_diagnostic(sut: VortraxSystem) -> None:
    _mock_shadow(load_fixture("vortrax", "shadow_get"))
    await sut.refresh()
    assert sut.devices["product_number"].entity_category == "diagnostic"


async def test_start_cleaning_uses_vortrax_namespace(
    sut: VortraxSystem,
) -> None:
    from iaqualink.systems.vr import system as vr_sys_mod

    with patch.object(vr_sys_mod, "send_set_state", new=AsyncMock()) as m:
        await sut.start_cleaning()
        m.assert_awaited_once_with(sut.aqualink, "SN42", 1, namespace="vortrax")
