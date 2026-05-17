from __future__ import annotations

import json
from functools import cache
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


@cache
def _collect_snapshot_props(cls: type) -> tuple[str, ...]:
    """Collect _own_snapshot_props from each class in the MRO using vars()
    so inheritance does not contaminate each class's own declaration."""
    props: list[str] = []
    seen: set[str] = set()
    for ancestor in reversed(cls.__mro__):
        for p in vars(ancestor).get("_own_snapshot_props", ()):
            if p not in seen:
                props.append(p)
                seen.add(p)
    return tuple(props)


def snapshot_devices(
    devices: dict[str, AqualinkDevice],
) -> dict[str, dict]:
    return {
        name: {
            "type": type(dev).__name__,
            **{p: getattr(dev, p) for p in _collect_snapshot_props(type(dev))},
        }
        for name, dev in devices.items()
    }
