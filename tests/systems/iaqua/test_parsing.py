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
