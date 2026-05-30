"""Tests for i2d_robot device classes."""

from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

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


# ── I2dRobot (HA vacuum) ─────────────────────────────────────────────────────


def _robot(state_code=0x01, error_code=0):
    from iaqualink.systems.i2d_robot.device import I2dRobot

    system = MagicMock()
    system.serial = "SN1"
    system._state_code = state_code
    system._error_code = error_code
    return I2dRobot(system, {"name": "robot", "state": state_code})


class TestI2dRobot(unittest.TestCase):
    def test_from_data_robot_is_robot(self):
        from iaqualink.device import AqualinkRobot
        from iaqualink.systems.i2d_robot.device import I2dRobot

        system = MagicMock()
        system.serial = "SN1"
        dev = I2dDevice.from_data(system, {"name": "robot", "state": 4})
        self.assertIsInstance(dev, I2dRobot)
        self.assertIsInstance(dev, AqualinkRobot)

    def test_activity_cleaning(self):
        from iaqualink.device import AqualinkRobotActivity as A

        self.assertIs(_robot(0x02).activity, A.CLEANING)
        self.assertIs(_robot(0x04).activity, A.CLEANING)

    def test_activity_paused(self):
        from iaqualink.device import AqualinkRobotActivity as A

        self.assertIs(_robot(0x0C).activity, A.PAUSED)

    def test_activity_docked(self):
        from iaqualink.device import AqualinkRobotActivity as A

        self.assertIs(_robot(0x01).activity, A.DOCKED)

    def test_activity_finished_is_idle(self):
        from iaqualink.device import AqualinkRobotActivity as A

        self.assertIs(_robot(0x03).activity, A.IDLE)

    def test_activity_error_state(self):
        from iaqualink.device import AqualinkRobotActivity as A

        self.assertIs(_robot(0x0D).activity, A.ERROR)

    def test_activity_error_code_overrides(self):
        from iaqualink.device import AqualinkRobotActivity as A

        self.assertIs(_robot(0x04, error_code=7).activity, A.ERROR)

    def test_capabilities(self):
        r = _robot()
        self.assertTrue(r.supports_start)
        self.assertTrue(r.supports_stop)
        self.assertTrue(r.supports_return)
        self.assertFalse(r.supports_pause)
        self.assertFalse(r.supports_fan_speed)
        self.assertFalse(r.supports_clean_spot)
        self.assertFalse(r.supports_locate)

    def test_no_fan_speed(self):
        r = _robot()
        self.assertIsNone(r.fan_speed)
        self.assertIsNone(r.fan_speed_list)


class TestI2dRobotCommands(unittest.IsolatedAsyncioTestCase):
    async def test_start_delegates(self):
        r = _robot()
        r.system.start_cleaning = AsyncMock()
        await r.start()
        r.system.start_cleaning.assert_awaited_once_with()

    async def test_stop_delegates(self):
        r = _robot()
        r.system.stop_cleaning = AsyncMock()
        await r.stop()
        r.system.stop_cleaning.assert_awaited_once_with()

    async def test_return_delegates(self):
        r = _robot()
        r.system.return_to_base = AsyncMock()
        await r.return_to_base()
        r.system.return_to_base.assert_awaited_once_with()


# ── i2d sensor HA metadata ───────────────────────────────────────────────────


def _sensor(name, state):
    system = MagicMock()
    system.serial = "SN1"
    return I2dDevice.from_data(system, {"name": name, "state": state})


class TestI2dSensorMetadata(unittest.TestCase):
    def test_time_remaining_min(self):
        s = _sensor("time_remaining_min", "20")
        self.assertEqual(s.device_class, "duration")
        self.assertEqual(s.unit_of_measurement, "min")
        self.assertEqual(s.state_class, "measurement")
        self.assertEqual(s.native_value, 20)

    def test_total_hours(self):
        s = _sensor("total_hours", "120")
        self.assertEqual(s.device_class, "duration")
        self.assertEqual(s.unit_of_measurement, "h")
        self.assertEqual(s.state_class, "total_increasing")
        self.assertEqual(s.native_value, 120)

    def test_error_code_numeric_diagnostic(self):
        s = _sensor("error_code", "0")
        self.assertEqual(s.native_value, 0)
        self.assertEqual(s.entity_category, "diagnostic")

    def test_identifiers_and_codes_diagnostic(self):
        for n in (
            "hardware_id",
            "firmware_id",
            "model_number",
            "state_code",
            "mode_code",
            "uptime_minutes",
        ):
            self.assertEqual(_sensor(n, "x").entity_category, "diagnostic")

    def test_mode_label_stays_primary(self):
        s = _sensor("mode", "quick_clean_floor_only_standard")
        self.assertIsNone(s.entity_category)
        self.assertEqual(s.native_value, "quick_clean_floor_only_standard")


class TestI2dBinarySensorMetadata(unittest.TestCase):
    def test_running_device_class_diagnostic(self):
        s = _sensor("running", 1)
        self.assertEqual(s.device_class, "running")
        self.assertEqual(s.entity_category, "diagnostic")

    def test_canister_full_problem(self):
        self.assertEqual(_sensor("canister_full", 1).device_class, "problem")
