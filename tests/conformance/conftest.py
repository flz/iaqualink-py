"""Shared conftest for conformance tests.

Aggregates fixture factories from all system modules and exposes them as
parametrized pytest fixtures. Each system provides factory functions that
return fixture dataclasses.
"""

from __future__ import annotations

from typing import Callable

import pytest

from ..conftest import dotstar, resp_200  # noqa: F401 — re-exported for test modules

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


# ---------------------------------------------------------------------------
# System factory imports — each returns lists of (id, factory) tuples
# ---------------------------------------------------------------------------

from ..systems.exo.factories import (
    exo_climate_factories,
    exo_device_factories,
    exo_sensor_factories,
    exo_switch_factories,
    exo_system_factories,
)
from ..systems.i2d.factories import (
    i2d_binary_sensor_factories,
    i2d_device_factories,
    i2d_fan_factories,
    i2d_number_factories,
    i2d_sensor_factories,
    i2d_switch_factories,
    i2d_system_factories,
)
from ..systems.iaqua.factories import (
    iaqua_binary_sensor_factories,
    iaqua_climate_factories,
    iaqua_device_factories,
    iaqua_light_factories,
    iaqua_number_factories,
    iaqua_sensor_factories,
    iaqua_switch_factories,
    iaqua_system_factories,
)


def _collect(
    *sources: list[tuple[str, Callable]],
) -> tuple[list[str], list[Callable]]:
    ids = []
    factories = []
    for source in sources:
        for id_, factory in source:
            ids.append(id_)
            factories.append(factory)
    return ids, factories


# ---------------------------------------------------------------------------
# Parametrized fixtures
# ---------------------------------------------------------------------------

_device_ids, _device_factories = _collect(
    exo_device_factories,
    i2d_device_factories,
    iaqua_device_factories,
)


@pytest.fixture(params=_device_factories, ids=_device_ids)
def device_fixture(request: pytest.FixtureRequest) -> DeviceFixture:
    return request.param()


_sensor_ids, _sensor_factories = _collect(
    exo_sensor_factories,
    i2d_sensor_factories,
    iaqua_sensor_factories,
)


@pytest.fixture(params=_sensor_factories, ids=_sensor_ids)
def sensor_fixture(request: pytest.FixtureRequest) -> SensorFixture:
    return request.param()


_binary_sensor_ids, _binary_sensor_factories = _collect(
    i2d_binary_sensor_factories,
    iaqua_binary_sensor_factories,
)


@pytest.fixture(params=_binary_sensor_factories, ids=_binary_sensor_ids)
def binary_sensor_fixture(
    request: pytest.FixtureRequest,
) -> BinarySensorFixture:
    return request.param()


_switch_ids, _switch_factories = _collect(
    exo_switch_factories,
    i2d_switch_factories,
    iaqua_switch_factories,
)


@pytest.fixture(params=_switch_factories, ids=_switch_ids)
def switch_fixture(request: pytest.FixtureRequest) -> SwitchFixture:
    return request.param()


_light_ids, _light_factories = _collect(
    iaqua_light_factories,
)


@pytest.fixture(params=_light_factories, ids=_light_ids)
def light_fixture(request: pytest.FixtureRequest) -> LightFixture:
    return request.param()


_climate_ids, _climate_factories = _collect(
    exo_climate_factories,
    iaqua_climate_factories,
)


@pytest.fixture(params=_climate_factories, ids=_climate_ids)
def climate_fixture(request: pytest.FixtureRequest) -> ClimateFixture:
    return request.param()


_number_ids, _number_factories = _collect(
    i2d_number_factories,
    iaqua_number_factories,
)


@pytest.fixture(params=_number_factories, ids=_number_ids)
def number_fixture(request: pytest.FixtureRequest) -> NumberFixture:
    return request.param()


_fan_ids, _fan_factories = _collect(
    i2d_fan_factories,
)


@pytest.fixture(params=_fan_factories, ids=_fan_ids)
def fan_fixture(request: pytest.FixtureRequest) -> FanFixture:
    return request.param()


_system_ids, _system_factories = _collect(
    exo_system_factories,
    i2d_system_factories,
    iaqua_system_factories,
)


@pytest.fixture(params=_system_factories, ids=_system_ids)
def system_fixture(request: pytest.FixtureRequest) -> SystemFixture:
    return request.param()

