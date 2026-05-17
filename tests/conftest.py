from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from iaqualink.client import AqualinkClient
from iaqualink.device import AqualinkDevice


@pytest.fixture
def client() -> AqualinkClient:
    return AqualinkClient("foo", "bar")


def load_fixture(system: str, endpoint: str) -> dict:
    path = Path(__file__).parent / "fixtures" / system / f"{endpoint}.json"
    return json.loads(path.read_text())


def make_response(data: dict) -> MagicMock:
    r = MagicMock()
    r.json.return_value = data
    return r


# Computed properties serialized alongside raw data to catch regressions in
# parsing logic that derives values from constructor args rather than data keys
# (e.g. I2dNumber min/max wired via min_key/max_key, I2dPump state_translated).
_SNAPSHOT_PROPS = (
    "state",
    "state_translated",
    "label",
    "is_on",
    "unit",
    "current_value",
    "min_value",
    "max_value",
    "step",
    "rpm_min",
    "rpm_max",
    "custom_speed_rpm",
)


def snapshot_devices(
    devices: dict[str, AqualinkDevice],
) -> dict[str, dict]:
    result = {}
    for name, dev in devices.items():
        entry: dict = {"type": type(dev).__name__, "data": dev.data}
        for prop in _SNAPSHOT_PROPS:
            try:
                entry[prop] = getattr(dev, prop)
            except AttributeError:
                pass
        result[name] = entry
    return result
