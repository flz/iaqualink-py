from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion

from iaqualink.system import AqualinkSystem

from ...conftest import load_fixture, snapshot_devices


@pytest.fixture
def system(client):
    data = {
        "id": "PQR789",
        "serial_number": "ROBOT001",
        "device_type": "i2d_robot",
        "name": "Polaris Robot",
    }
    return AqualinkSystem.from_data(client, data=data)


def test_parse_status(system, snapshot: SnapshotAssertion) -> None:
    system._parse_status_response(load_fixture("i2d_robot", "control_status"))
    assert snapshot_devices(system.devices) == snapshot
