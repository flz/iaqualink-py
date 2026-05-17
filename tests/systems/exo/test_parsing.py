from __future__ import annotations

import pytest
from syrupy.assertion import SnapshotAssertion

from iaqualink.system import AqualinkSystem

from ...conftest import load_fixture, make_response, snapshot_devices


@pytest.fixture
def system(client):
    data = {
        "id": 1,
        "serial_number": "ABCDEFG",
        "device_type": "exo",
        "name": "Pool",
    }
    return AqualinkSystem.from_data(client, data=data)


def test_parse_shadow(system, snapshot: SnapshotAssertion) -> None:
    system._parse_shadow_response(
        make_response(load_fixture("exo", "shadow_get"))
    )
    assert snapshot_devices(system.devices) == snapshot
