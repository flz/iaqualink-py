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


def test_parse_main_plus_filt_sub_shadow(
    system, snapshot: SnapshotAssertion
) -> None:
    system._parse_shadow_response(
        make_response(load_fixture("tcx", "synthetic_main_shadow"))
    )
    system._parse_sub_shadow_response(
        "_filt",
        make_response(load_fixture("tcx", "synthetic_filt_shadow")),
    )
    assert snapshot_devices(system.devices) == snapshot


def test_parse_main_plus_fea_sub_shadow(
    system, snapshot: SnapshotAssertion
) -> None:
    system._parse_shadow_response(
        make_response(load_fixture("tcx", "synthetic_main_shadow"))
    )
    system._parse_sub_shadow_response(
        "_fea",
        make_response(load_fixture("tcx", "synthetic_fea_shadow")),
    )
    assert snapshot_devices(system.devices) == snapshot
