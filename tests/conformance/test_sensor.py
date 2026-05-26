"""Conformance tests for AqualinkSensor contract."""

from __future__ import annotations

from iaqualink.device import AqualinkSensor

from .fixtures import SensorFixture


def test_inheritance(sensor_fixture: SensorFixture) -> None:
    assert isinstance(sensor_fixture.device, AqualinkSensor)


def test_property_value(sensor_fixture: SensorFixture) -> None:
    assert isinstance(sensor_fixture.device.value, str)


def test_from_data(sensor_fixture: SensorFixture) -> None:
    if sensor_fixture.expected_class is not None:
        assert isinstance(sensor_fixture.device, sensor_fixture.expected_class)
