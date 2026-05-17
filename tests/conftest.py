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


def snapshot_devices(
    devices: dict[str, AqualinkDevice],
) -> dict[str, dict]:
    return {
        name: {"type": type(dev).__name__, "data": dev.data}
        for name, dev in devices.items()
    }
