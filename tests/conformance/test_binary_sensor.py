"""Conformance tests for AqualinkBinarySensor contract."""

from __future__ import annotations

from iaqualink.device import AqualinkBinarySensor

from .fixtures import BinarySensorFixture


def test_inheritance(binary_sensor_fixture: BinarySensorFixture) -> None:
    assert isinstance(binary_sensor_fixture.device_on, AqualinkBinarySensor)


def test_property_is_on_true(
    binary_sensor_fixture: BinarySensorFixture,
) -> None:
    assert binary_sensor_fixture.device_on.is_on is True


def test_property_is_on_false(
    binary_sensor_fixture: BinarySensorFixture,
) -> None:
    assert binary_sensor_fixture.device_off.is_on is False


def test_from_data(binary_sensor_fixture: BinarySensorFixture) -> None:
    if binary_sensor_fixture.expected_class is not None:
        assert isinstance(
            binary_sensor_fixture.device_on,
            binary_sensor_fixture.expected_class,
        )
