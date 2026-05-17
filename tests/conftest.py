from __future__ import annotations

import json
from enum import Enum
from functools import cache
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import iaqualink.device as _dev
from iaqualink.client import AqualinkClient
from iaqualink.device import AqualinkDevice

# Abstract base classes whose @property definitions constitute the HA-facing
# public API. Introspected at test time — no production code annotation needed.
_API_CLASSES = frozenset(
    {
        _dev.AqualinkDevice,
        _dev.AqualinkSensor,
        _dev.AqualinkBinarySensor,
        _dev.AqualinkSwitch,
        _dev.AqualinkLight,
        _dev.AqualinkThermostat,
        _dev.AqualinkNumber,
        _dev.AqualinkPump,
    }
)

# Properties excluded from snapshots: identity, capability flags, and config
# ranges that are not per-poll observable state.
_SNAPSHOT_EXCLUDE = frozenset(
    {
        "name",
        "manufacturer",
        "model",
        "state_enum",
        "supports_turn_on",
        "supports_turn_off",
        "supports_brightness",
        "supports_effect",
        "supports_presets",
        "supports_set_speed_percentage",
        "max_temperature",
        "min_temperature",
    }
)


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
    """Collect public @property names from API base classes, base-first.

    Uses vars() instead of getattr so each class's own __dict__ is inspected
    in isolation — inheritance doesn't contaminate the per-class view.
    """
    props: list[str] = []
    seen: set[str] = set()
    for ancestor in reversed(cls.__mro__):
        if ancestor not in _API_CLASSES:
            continue
        for attr, val in vars(ancestor).items():
            if not isinstance(val, property):
                continue
            if attr.startswith("_") or attr in _SNAPSHOT_EXCLUDE:
                continue
            if attr not in seen:
                props.append(attr)
                seen.add(attr)
    return tuple(props)


def _serialize(v: object) -> object:
    """Render enum instances as their wire-level value."""
    if isinstance(v, Enum):
        return v.value
    return v


def snapshot_devices(
    devices: dict[str, AqualinkDevice],
) -> dict[str, dict]:
    return {
        name: {
            "type": type(dev).__name__,
            **{
                p: _serialize(getattr(dev, p))
                for p in _collect_snapshot_props(type(dev))
            },
        }
        for name, dev in devices.items()
    }
