from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion

from iaqualink.system import AqualinkSystem

from ...conftest import load_fixture, make_response, snapshot_devices


@pytest.fixture
def system(client):
    data = {
        "id": 123456,
        "serial_number": "SN123456",
        "device_type": "iaqua",
        "name": "Pool",
    }
    return AqualinkSystem.from_data(client, data=data)


def test_parse_home(system, snapshot: SnapshotAssertion) -> None:
    system._parse_home_response(
        make_response(load_fixture("iaqua", "session_get_home"))
    )
    assert snapshot_devices(system.devices) == snapshot


def test_parse_devices(system, snapshot: SnapshotAssertion) -> None:
    system._parse_home_response(
        make_response(load_fixture("iaqua", "session_get_home"))
    )
    system._parse_devices_response(
        make_response(load_fixture("iaqua", "session_get_devices"))
    )
    assert snapshot_devices(system.devices) == snapshot


def test_parse_onetouch(system, snapshot: SnapshotAssertion) -> None:
    system._parse_onetouch_response(
        make_response(load_fixture("iaqua", "session_get_onetouch"))
    )
    assert snapshot_devices(system.devices) == snapshot


def test_parse_devices_icl_zones(system, snapshot: SnapshotAssertion) -> None:
    system._parse_home_response(
        make_response(load_fixture("iaqua", "session_get_home"))
    )
    system._parse_devices_response(
        make_response(load_fixture("iaqua", "session_get_devices_icl_zones"))
    )
    assert snapshot_devices(system.devices) == snapshot


def test_parse_swc_config(system, snapshot: SnapshotAssertion) -> None:
    system._parse_home_response(
        make_response(load_fixture("iaqua", "session_get_home"))
    )
    system._parse_devices_response(
        make_response(load_fixture("iaqua", "session_get_devices"))
    )
    system._parse_swc_config_response(
        make_response(load_fixture("iaqua", "session_get_swc_config"))
    )
    assert snapshot_devices(system.devices) == snapshot


def test_parse_swc_config_boost_on(system, snapshot: SnapshotAssertion) -> None:
    system._parse_home_response(
        make_response(load_fixture("iaqua", "session_get_home"))
    )
    system._parse_devices_response(
        make_response(load_fixture("iaqua", "session_get_devices"))
    )
    system._parse_swc_config_response(
        make_response(load_fixture("iaqua", "session_get_swc_config"))
    )
    system._parse_swc_config_response(
        make_response(load_fixture("iaqua", "session_control_swc_boost"))
    )
    assert snapshot_devices(system.devices) == snapshot


def test_parse_swc_config_after_set(
    system, snapshot: SnapshotAssertion
) -> None:
    system._parse_home_response(
        make_response(load_fixture("iaqua", "session_get_home"))
    )
    system._parse_devices_response(
        make_response(load_fixture("iaqua", "session_get_devices"))
    )
    system._parse_swc_config_response(
        make_response(load_fixture("iaqua", "session_get_swc_config"))
    )
    system._parse_swc_config_response(
        make_response(load_fixture("iaqua", "session_set_swc_config"))
    )
    assert snapshot_devices(system.devices) == snapshot
