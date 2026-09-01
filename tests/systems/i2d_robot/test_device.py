"""Tests for i2d_robot device classes.

Generic device/sensor/binary-sensor contract behaviour is covered by the
conformance suite via ``i2d_robot_*_factories``. This module keeps the
i2d_robot-specific property, from_data dispatch, robot-activity/capability,
command-delegation, and HA-metadata assertions.
"""

from __future__ import annotations

import unittest
from typing import Any, cast
from unittest.mock import AsyncMock

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkSensor,
    AqualinkVacuum,
)
from iaqualink.enums import AqualinkRobotActivity
from iaqualink.systems.i2d_robot.device import (
    I2dBinarySensor,
    I2dDevice,
    I2dRobot,
    I2dSensor,
)
from iaqualink.systems.i2d_robot.system import I2dRobotSystem

from .factories import make_system


def _device_data(name: str, state: object) -> dict[str, Any]:
    """Build raw device data; ``dict[str, Any]`` satisfies ``DeviceData``."""
    return {"name": name, "state": state}


def _system() -> I2dRobotSystem:
    return make_system()


# ---------------------------------------------------------------------------
# Device property surface
# ---------------------------------------------------------------------------


class TestI2dDeviceProperties(unittest.TestCase):
    def setUp(self) -> None:
        self.system = _system()

    def test_sensor_name(self) -> None:
        d = I2dSensor(self.system, _device_data("time_remaining_min", 30))
        assert d.name == "time_remaining_min"

    def test_sensor_label_capitalization(self) -> None:
        d = I2dSensor(self.system, _device_data("time_remaining_min", 30))
        assert d.label == "Time Remaining Min"

    def test_sensor_manufacturer(self) -> None:
        d = I2dSensor(self.system, _device_data("state", "idle_or_docked"))
        assert d.manufacturer == "Polaris"

    def test_binary_sensor_manufacturer(self) -> None:
        d = I2dBinarySensor(self.system, _device_data("running", 0))
        assert d.manufacturer == "Polaris"

    def test_sensor_model(self) -> None:
        d = I2dSensor(self.system, _device_data("state", "idle_or_docked"))
        assert d.model == "Sensor"

    def test_binary_sensor_model(self) -> None:
        d = I2dBinarySensor(self.system, _device_data("canister_full", 0))
        assert d.model == "BinarySensor"

    def test_sensor_value(self) -> None:
        d = I2dSensor(self.system, _device_data("state", "actively_cleaning"))
        assert d.value == "actively_cleaning"

    def test_sensor_value_numeric(self) -> None:
        d = I2dSensor(self.system, _device_data("mode_code", 10))
        assert d.value == "10"

    def test_sensor_numeric_value_non_numeric_returns_none(self) -> None:
        # A numeric-typed sensor whose raw value can't be coerced -> None.
        d = I2dSensor(self.system, _device_data("time_remaining_min", "oops"))
        assert d.value is None

    def test_binary_sensor_is_on_true(self) -> None:
        d = I2dBinarySensor(self.system, _device_data("running", 1))
        assert d.is_on is True

    def test_binary_sensor_is_on_false(self) -> None:
        d = I2dBinarySensor(self.system, _device_data("running", 0))
        assert d.is_on is False


# ---------------------------------------------------------------------------
# from_data dispatch
# ---------------------------------------------------------------------------


class TestI2dFromData(unittest.TestCase):
    def setUp(self) -> None:
        self.system = _system()

    def _from_data(self, name: str, state: object) -> AqualinkDevice:
        return I2dDevice.from_data(self.system, _device_data(name, state))

    def test_from_data_running_returns_binary_sensor(self) -> None:
        device = self._from_data("running", 1)
        assert isinstance(device, I2dBinarySensor)
        assert isinstance(device, AqualinkBinarySensor)

    def test_from_data_canister_full_returns_binary_sensor(self) -> None:
        device = self._from_data("canister_full", 0)
        assert isinstance(device, I2dBinarySensor)
        assert isinstance(device, AqualinkBinarySensor)

    def test_from_data_state_returns_sensor(self) -> None:
        device = self._from_data("state", "idle_or_docked")
        assert isinstance(device, I2dSensor)
        assert isinstance(device, AqualinkSensor)

    def test_from_data_mode_returns_sensor(self) -> None:
        device = self._from_data("mode", "quick_clean_floor_only_standard")
        assert isinstance(device, I2dSensor)

    def test_from_data_generic_returns_sensor(self) -> None:
        device = self._from_data("time_remaining_min", 25)
        assert isinstance(device, I2dSensor)

    def test_from_data_robot_is_robot(self) -> None:
        dev = self._from_data("robot", 4)
        assert isinstance(dev, I2dRobot)
        assert isinstance(dev, AqualinkVacuum)


# ---------------------------------------------------------------------------
# I2dRobot (HA vacuum)
# ---------------------------------------------------------------------------


def _robot(state_code: int = 0x01, error_code: int = 0) -> I2dRobot:
    system = make_system()
    system._state_code = state_code
    system._error_code = error_code
    return I2dRobot(system, _device_data("robot", state_code))


class TestI2dRobot(unittest.TestCase):
    def test_activity_cleaning(self) -> None:
        assert _robot(0x02).activity is AqualinkRobotActivity.CLEANING
        assert _robot(0x04).activity is AqualinkRobotActivity.CLEANING

    def test_activity_paused(self) -> None:
        assert _robot(0x0C).activity is AqualinkRobotActivity.PAUSED

    def test_activity_docked(self) -> None:
        assert _robot(0x01).activity is AqualinkRobotActivity.DOCKED

    def test_activity_finished_is_idle(self) -> None:
        assert _robot(0x03).activity is AqualinkRobotActivity.IDLE

    def test_activity_error_state(self) -> None:
        assert _robot(0x0D).activity is AqualinkRobotActivity.ERROR

    def test_activity_error_code_overrides(self) -> None:
        assert (
            _robot(0x04, error_code=7).activity is AqualinkRobotActivity.ERROR
        )

    def test_capabilities(self) -> None:
        r = _robot()
        assert r.supports_start is True
        assert r.supports_stop is True
        assert r.supports_return is True
        assert r.supports_pause is False
        assert r.supports_fan_speed is False
        assert r.supports_clean_spot is False
        assert r.supports_locate is False

    def test_no_fan_speed(self) -> None:
        r = _robot()
        assert r.fan_speed is None
        assert r.fan_speed_list == []
        assert r.supports_fan_speed is False


class TestI2dRobotCommands(unittest.IsolatedAsyncioTestCase):
    async def test_start_delegates(self) -> None:
        r = _robot()
        mock = AsyncMock()
        r.system.start_cleaning = mock  # type: ignore[method-assign]  # ty: ignore
        await r.start()
        mock.assert_awaited_once_with()

    async def test_stop_delegates(self) -> None:
        r = _robot()
        mock = AsyncMock()
        r.system.stop_cleaning = mock  # type: ignore[method-assign]  # ty: ignore
        await r.stop()
        mock.assert_awaited_once_with()

    async def test_return_delegates(self) -> None:
        r = _robot()
        mock = AsyncMock()
        r.system.return_to_base = mock  # type: ignore[method-assign]  # ty: ignore
        await r.return_to_base()
        mock.assert_awaited_once_with()


# ---------------------------------------------------------------------------
# i2d sensor / binary-sensor HA metadata
# ---------------------------------------------------------------------------


def _sensor(name: str, state: object) -> AqualinkDevice:
    system = make_system()
    return I2dDevice.from_data(system, _device_data(name, state))


class TestI2dSensorMetadata(unittest.TestCase):
    def test_time_remaining_min(self) -> None:
        s = cast(I2dSensor, _sensor("time_remaining_min", "20"))
        assert s.device_class == "duration"
        assert s.unit_of_measurement == "min"
        assert s.state_class == "measurement"
        assert s.value == 20

    def test_total_hours(self) -> None:
        s = cast(I2dSensor, _sensor("total_hours", "120"))
        assert s.device_class == "duration"
        assert s.unit_of_measurement == "h"
        assert s.state_class == "total_increasing"
        assert s.value == 120

    def test_error_code_numeric_diagnostic(self) -> None:
        s = cast(I2dSensor, _sensor("error_code", "0"))
        assert s.value == 0
        assert s.entity_category == "diagnostic"

    def test_identifiers_and_codes_diagnostic(self) -> None:
        for n in (
            "hardware_id",
            "firmware_id",
            "model_number",
            "state_code",
            "mode_code",
            "uptime_minutes",
        ):
            assert _sensor(n, "x").entity_category == "diagnostic"

    def test_mode_label_stays_primary(self) -> None:
        s = cast(I2dSensor, _sensor("mode", "quick_clean_floor_only_standard"))
        assert s.entity_category is None
        assert s.value == "quick_clean_floor_only_standard"


class TestI2dBinarySensorMetadata(unittest.TestCase):
    def test_running_device_class_diagnostic(self) -> None:
        s = cast(I2dBinarySensor, _sensor("running", 1))
        assert s.device_class == "running"
        assert s.entity_category == "diagnostic"

    def test_canister_full_problem(self) -> None:
        s = cast(I2dBinarySensor, _sensor("canister_full", 1))
        assert s.device_class == "problem"
