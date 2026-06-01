"""Conformance tests for AqualinkDevice base contract."""

from __future__ import annotations

import copy

from iaqualink.device import AqualinkDevice

from .fixtures import DeviceFixture


def test_property_name(device_fixture: DeviceFixture) -> None:
    assert isinstance(device_fixture.device.name, str)


def test_property_label(device_fixture: DeviceFixture) -> None:
    assert isinstance(device_fixture.device.label, str)


def test_property_manufacturer(device_fixture: DeviceFixture) -> None:
    assert isinstance(device_fixture.device.manufacturer, str)


def test_property_model(device_fixture: DeviceFixture) -> None:
    assert isinstance(device_fixture.device.model, str)


def test_from_data(device_fixture: DeviceFixture) -> None:
    if device_fixture.expected_class is not None:
        assert isinstance(device_fixture.device, device_fixture.expected_class)


def test_is_aqualink_device(device_fixture: DeviceFixture) -> None:
    assert isinstance(device_fixture.device, AqualinkDevice)


def test_equal_reflexive(device_fixture: DeviceFixture) -> None:
    assert device_fixture.device == device_fixture.device


def test_not_equal_different_type(device_fixture: DeviceFixture) -> None:
    assert (device_fixture.device == {}) is False


def test_not_equal_different_name(device_fixture: DeviceFixture) -> None:
    other = copy.deepcopy(device_fixture.device)
    other.data["name"] = "__different__"
    assert device_fixture.device != other
