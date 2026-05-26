"""Tests for i2d_robot device classes."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from iaqualink.device import AqualinkBinarySensor, AqualinkSensor
from iaqualink.systems.i2d_robot.device import (
    I2dBinarySensor,
    I2dDevice,
    I2dSensor,
)

from ...base_test_device import TestBaseBinarySensor, TestBaseSensor

_SYSTEM_DATA = {
    "id": "ABC123",
    "serial_number": "ABC123",
    "name": "My Robot",
    "device_type": "i2d_robot",
}


def _make_system(client):  # type: ignore[no-untyped-def]
    # Import here to avoid circular issues; system module registered in client.
    from iaqualink.systems.i2d_robot.system import I2dRobotSystem

    return I2dRobotSystem(client, _SYSTEM_DATA)


class TestI2dSensorContract(TestBaseSensor):
    def setUp(self) -> None:
        super().setUp()
        system = _make_system(self.client)
        self.sut = I2dSensor(
            system, {"name": "state", "state": "actively_cleaning"}
        )
        self.sut_class = I2dSensor


class TestI2dBinarySensorContract(TestBaseBinarySensor):
    def setUp(self) -> None:
        super().setUp()
        system = _make_system(self.client)
        self._data: dict = {"name": "running", "state": 1}
        self.sut = I2dBinarySensor(system, self._data)
        self.sut_class = I2dBinarySensor

    def test_property_is_on_true(self) -> None:
        self._data["state"] = 1
        assert self.sut.is_on is True

    def test_property_is_on_false(self) -> None:
        self._data["state"] = 0
        assert self.sut.is_on is False


class TestI2dDeviceProperties(unittest.TestCase):
    def setUp(self) -> None:
        self.client = MagicMock()
        self.system = MagicMock()

    def test_sensor_name(self) -> None:
        d = I2dSensor(self.system, {"name": "time_remaining_min", "state": 30})
        assert d.name == "time_remaining_min"

    def test_sensor_label_capitalization(self) -> None:
        d = I2dSensor(self.system, {"name": "time_remaining_min", "state": 30})
        assert d.label == "Time Remaining Min"

    def test_sensor_manufacturer(self) -> None:
        d = I2dSensor(self.system, {"name": "state", "state": "idle_or_docked"})
        assert d.manufacturer == "Polaris"

    def test_binary_sensor_manufacturer(self) -> None:
        d = I2dBinarySensor(self.system, {"name": "running", "state": 0})
        assert d.manufacturer == "Polaris"

    def test_sensor_model(self) -> None:
        d = I2dSensor(self.system, {"name": "state", "state": "idle_or_docked"})
        assert d.model == "Sensor"

    def test_binary_sensor_model(self) -> None:
        d = I2dBinarySensor(self.system, {"name": "canister_full", "state": 0})
        assert d.model == "BinarySensor"

    def test_sensor_value(self) -> None:
        d = I2dSensor(
            self.system, {"name": "state", "state": "actively_cleaning"}
        )
        assert d.value == "actively_cleaning"

    def test_sensor_value_numeric(self) -> None:
        d = I2dSensor(self.system, {"name": "mode_code", "state": 10})
        assert d.value == "10"

    def test_binary_sensor_is_on_true(self) -> None:
        d = I2dBinarySensor(self.system, {"name": "running", "state": 1})
        assert d.is_on is True

    def test_binary_sensor_is_on_false(self) -> None:
        d = I2dBinarySensor(self.system, {"name": "running", "state": 0})
        assert d.is_on is False


class TestI2dFromData(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        from iaqualink.client import AqualinkClient

        self.client = AqualinkClient("foo", "bar")
        self.addAsyncCleanup(self.client.close)

    def _make_system(self):  # type: ignore[no-untyped-def]
        return _make_system(self.client)

    def test_from_data_running_returns_binary_sensor(self) -> None:
        system = self._make_system()
        device = I2dDevice.from_data(system, {"name": "running", "state": 1})
        assert isinstance(device, I2dBinarySensor)
        assert isinstance(device, AqualinkBinarySensor)

    def test_from_data_canister_full_returns_binary_sensor(self) -> None:
        system = self._make_system()
        device = I2dDevice.from_data(
            system, {"name": "canister_full", "state": 0}
        )
        assert isinstance(device, I2dBinarySensor)
        assert isinstance(device, AqualinkBinarySensor)

    def test_from_data_state_returns_sensor(self) -> None:
        system = self._make_system()
        device = I2dDevice.from_data(
            system, {"name": "state", "state": "idle_or_docked"}
        )
        assert isinstance(device, I2dSensor)
        assert isinstance(device, AqualinkSensor)

    def test_from_data_mode_returns_sensor(self) -> None:
        system = self._make_system()
        device = I2dDevice.from_data(
            system,
            {"name": "mode", "state": "quick_clean_floor_only_standard"},
        )
        assert isinstance(device, I2dSensor)

    def test_from_data_generic_returns_sensor(self) -> None:
        system = self._make_system()
        device = I2dDevice.from_data(
            system, {"name": "time_remaining_min", "state": 25}
        )
        assert isinstance(device, I2dSensor)
