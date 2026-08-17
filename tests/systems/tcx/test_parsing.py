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
        "device_type": "tcx",
        "name": "Pool",
    }
    return AqualinkSystem.from_data(client, data=data)


def test_parse_main_shadow(system, snapshot: SnapshotAssertion) -> None:
    system._parse_shadow_response(
        make_response(load_fixture("tcx", "synthetic_main_shadow"))
    )
    assert snapshot_devices(system.devices) == snapshot


def test_parse_main_plus_fea_delta(system, snapshot: SnapshotAssertion) -> None:
    # Feature-circuit discovery used to only run against a dedicated REST
    # sub-shadow response; that REST fetch is confirmed non-functional
    # against real hardware and has been removed. It now runs best-effort
    # against the unified reported tree, so simulate a WS delta carrying the
    # same feaCircuitN keys the old sub-shadow response used to.
    system._parse_shadow_response(
        make_response(load_fixture("tcx", "synthetic_main_shadow"))
    )
    fea_delta = load_fixture("tcx", "synthetic_fea_shadow")["state"]["reported"]
    system._apply_reported_delta(fea_delta)
    assert snapshot_devices(system.devices) == snapshot
