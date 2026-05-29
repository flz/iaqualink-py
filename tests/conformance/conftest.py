"""Shared conftest for conformance tests.

Aggregates fixture factories from all system modules and exposes them as
parametrized pytest fixtures. Each system provides factory functions that
return fixture dataclasses.

Convention: ``tests/systems/<name>/factories.py`` must export lists named
``<name>_<type>_factories`` (e.g. ``iaqua_switch_factories``) containing
``(id_string, factory_callable)`` tuples. The conftest discovers them
automatically — no manual import needed when adding a new system.
"""

from __future__ import annotations

import importlib
import pathlib
import warnings
from typing import Callable

import pytest

from ..conftest import (  # noqa: F401 — re-exported for test modules
    dotstar,
    resp_200,
)
from .fixtures import (
    BinarySensorFixture,
    ClimateFixture,
    DeviceFixture,
    FanFixture,
    LightFixture,
    NumberFixture,
    SensorFixture,
    SwitchFixture,
    SystemFixture,
)

_FIXTURE_TYPES = (
    "device",
    "sensor",
    "binary_sensor",
    "switch",
    "light",
    "climate",
    "number",
    "fan",
    "system",
)

_systems_root = pathlib.Path(__file__).parent.parent / "systems"


def _discover_factories(fixture_type: str) -> tuple[list[str], list[Callable]]:
    """Scan all ``tests/systems/*/factories.py`` for ``<system>_<type>_factories``.

    Each factories.py must explicitly declare every fixture type list, even if
    empty (``exo_light_factories: list = []``). A missing attribute is a likely
    typo and triggers a warning at collection time.
    """
    ids: list[str] = []
    factories: list[Callable] = []
    for pkg in sorted(_systems_root.iterdir()):
        if not pkg.is_dir() or not (pkg / "factories.py").exists():
            continue
        mod = importlib.import_module(f"tests.systems.{pkg.name}.factories")
        attr = f"{pkg.name}_{fixture_type}_factories"
        factory_list = getattr(mod, attr, None)
        if factory_list is None:
            warnings.warn(
                f"{mod.__name__} is missing '{attr}'. "
                "Add an empty list if this device type is not supported.",
                stacklevel=2,
            )
            continue
        for id_, factory in factory_list:
            ids.append(id_)
            factories.append(factory)
    return ids, factories


# ---------------------------------------------------------------------------
# Parametrized fixtures — one per fixture type
# ---------------------------------------------------------------------------

_device_ids, _device_factories = _discover_factories("device")


@pytest.fixture(params=_device_factories, ids=_device_ids)
def device_fixture(request: pytest.FixtureRequest) -> DeviceFixture:
    return request.param()


_sensor_ids, _sensor_factories = _discover_factories("sensor")


@pytest.fixture(params=_sensor_factories, ids=_sensor_ids)
def sensor_fixture(request: pytest.FixtureRequest) -> SensorFixture:
    return request.param()


_binary_sensor_ids, _binary_sensor_factories = _discover_factories(
    "binary_sensor"
)


@pytest.fixture(params=_binary_sensor_factories, ids=_binary_sensor_ids)
def binary_sensor_fixture(
    request: pytest.FixtureRequest,
) -> BinarySensorFixture:
    return request.param()


_switch_ids, _switch_factories = _discover_factories("switch")


@pytest.fixture(params=_switch_factories, ids=_switch_ids)
def switch_fixture(request: pytest.FixtureRequest) -> SwitchFixture:
    return request.param()


_light_ids, _light_factories = _discover_factories("light")


@pytest.fixture(params=_light_factories, ids=_light_ids)
def light_fixture(request: pytest.FixtureRequest) -> LightFixture:
    return request.param()


_climate_ids, _climate_factories = _discover_factories("climate")


@pytest.fixture(params=_climate_factories, ids=_climate_ids)
def climate_fixture(request: pytest.FixtureRequest) -> ClimateFixture:
    return request.param()


_number_ids, _number_factories = _discover_factories("number")


@pytest.fixture(params=_number_factories, ids=_number_ids)
def number_fixture(request: pytest.FixtureRequest) -> NumberFixture:
    return request.param()


_fan_ids, _fan_factories = _discover_factories("fan")


@pytest.fixture(params=_fan_factories, ids=_fan_ids)
def fan_fixture(request: pytest.FixtureRequest) -> FanFixture:
    return request.param()


_system_ids, _system_factories = _discover_factories("system")


@pytest.fixture(params=_system_factories, ids=_system_ids)
def system_fixture(request: pytest.FixtureRequest) -> SystemFixture:
    return request.param()
