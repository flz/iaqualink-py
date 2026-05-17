from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion

from iaqualink.system import AqualinkSystem

from ...conftest import load_fixture, make_response, snapshot_devices


@pytest.fixture
def system(client):
    data = {
        "id": 1,
        "serial_number": "ABC123",
        "name": "Pool Pump",
        "device_type": "i2d",
    }
    return AqualinkSystem.from_data(client, data=data)


def test_parse_alldata(system, snapshot: SnapshotAssertion) -> None:
    system._parse_alldata_response(
        make_response(load_fixture("i2d", "control_alldata_read"))
    )
    assert snapshot_devices(system.devices) == snapshot
