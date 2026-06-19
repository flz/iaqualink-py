from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion

from iaqualink.system import AqualinkSystem

from ...conftest import load_fixture, make_response, snapshot_devices


@pytest.fixture
def system(client):
    data = {
        "id": "CV3000",
        "serial_number": "SN42",
        "device_type": "cyclobat",
        "name": "Pool Robot",
    }
    return AqualinkSystem.from_data(client, data=data)


def test_parse_shadow(system, snapshot: SnapshotAssertion) -> None:
    system._parse_shadow_response(
        make_response(load_fixture("cyclobat", "shadow_get"))
    )
    assert snapshot_devices(system.devices) == snapshot
