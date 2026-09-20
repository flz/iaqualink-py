from __future__ import annotations

import unittest
from typing import Any, cast
from unittest.mock import AsyncMock

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkSensor,
)
from iaqualink.systems.cyclonext.device import (
    CyclonextBinarySensor,
    CyclonextDevice,
    CyclonextErrorSensor,
    CyclonextRobot,
    CyclonextSensor,
)

from .factories import make_system


def _device_data(name: str, state: object) -> dict[str, Any]:
    """Build raw device data; ``dict[str, Any]`` satisfies ``DeviceData``."""
    return {"name": name, "state": state}


class TestCyclonextDeviceFromData(unittest.TestCase):
    def setUp(self) -> None:
        self.system = make_system()

    def _from_data(self, name: str, state: object) -> AqualinkDevice:
        return CyclonextDevice.from_data(self.system, _device_data(name, state))

    # from_data routing
    def test_from_data_running_is_binary_sensor(self) -> None:
        dev = self._from_data("running", 1)
        self.assertIsInstance(dev, CyclonextBinarySensor)
        self.assertIsInstance(dev, AqualinkBinarySensor)

    def test_from_data_error_code_is_error_sensor(self) -> None:
        dev = self._from_data("error_code", 0)
        self.assertIsInstance(dev, CyclonextErrorSensor)
        self.assertIsInstance(dev, AqualinkSensor)

    def test_from_data_mode_is_sensor(self) -> None:
        dev = self._from_data("mode", 1)
        self.assertIsInstance(dev, CyclonextSensor)
        self.assertIsInstance(dev, AqualinkSensor)

    # label
    def test_label_underscores_to_title_case(self) -> None:
        dev = self._from_data("control_box_vr", 0)
        self.assertEqual(dev.label, "Control Box Vr")

    def test_label_single_word(self) -> None:
        dev = self._from_data("running", 1)
        self.assertEqual(dev.label, "Running")

    # manufacturer
    def test_manufacturer_zodiac_sensor(self) -> None:
        dev = self._from_data("mode", 1)
        self.assertEqual(dev.manufacturer, "Zodiac")

    def test_manufacturer_zodiac_binary(self) -> None:
        dev = self._from_data("running", 0)
        self.assertEqual(dev.manufacturer, "Zodiac")

    def test_manufacturer_zodiac_error(self) -> None:
        dev = self._from_data("error_code", 0)
        self.assertEqual(dev.manufacturer, "Zodiac")

    # model
    def test_model_binary_sensor_strips_prefix(self) -> None:
        dev = CyclonextBinarySensor(self.system, _device_data("running", 1))
        self.assertEqual(dev.model, "BinarySensor")

    def test_model_error_sensor_strips_prefix(self) -> None:
        dev = CyclonextErrorSensor(self.system, _device_data("error_code", 0))
        self.assertEqual(dev.model, "ErrorSensor")

    def test_model_sensor_strips_prefix(self) -> None:
        dev = CyclonextSensor(self.system, _device_data("mode", 1))
        self.assertEqual(dev.model, "Sensor")

    # is_on
    def test_binary_sensor_is_on_true(self) -> None:
        dev = CyclonextBinarySensor(self.system, _device_data("running", 1))
        self.assertTrue(dev.is_on)

    def test_binary_sensor_is_on_false(self) -> None:
        dev = CyclonextBinarySensor(self.system, _device_data("running", 0))
        self.assertFalse(dev.is_on)

    # value
    def test_sensor_value_stringified(self) -> None:
        dev = CyclonextSensor(self.system, _device_data("mode", "v1.2.3"))
        self.assertEqual(dev.value, "v1.2.3")

    def test_error_sensor_value_numeric(self) -> None:
        dev = CyclonextErrorSensor(self.system, _device_data("error_code", 5))
        self.assertEqual(dev.value, 5)


# ── CyclonextRobot (HA vacuum) ───────────────────────────────────────────────


def _robot(robot_state: dict[str, Any] | None = None) -> CyclonextRobot:
    system = make_system()
    system._robot_state = robot_state if robot_state is not None else {}
    return CyclonextRobot(system, _device_data("robot", 0))


class TestCyclonextRobot(unittest.TestCase):
    def test_from_data_robot_is_robot(self):
        from iaqualink.device import AqualinkVacuum

        system = make_system()
        dev = CyclonextDevice.from_data(system, _device_data("robot", 1))
        self.assertIsInstance(dev, CyclonextRobot)
        self.assertIsInstance(dev, AqualinkVacuum)

    def test_activity_cleaning(self):
        from iaqualink.enums import AqualinkRobotActivity

        self.assertIs(
            _robot({"mode": 1}).activity, AqualinkRobotActivity.CLEANING
        )

    def test_activity_remote_is_paused(self):
        from iaqualink.enums import AqualinkRobotActivity

        self.assertIs(
            _robot({"mode": 2}).activity, AqualinkRobotActivity.PAUSED
        )

    def test_activity_lift_is_idle(self):
        from iaqualink.enums import AqualinkRobotActivity

        self.assertIs(_robot({"mode": 3}).activity, AqualinkRobotActivity.IDLE)

    def test_activity_stopped_is_idle(self):
        from iaqualink.enums import AqualinkRobotActivity

        self.assertIs(_robot({"mode": 0}).activity, AqualinkRobotActivity.IDLE)

    def test_activity_error_overrides_mode(self):
        from iaqualink.enums import AqualinkRobotActivity

        self.assertIs(
            _robot({"mode": 1, "errors": {"code": 9}}).activity,
            AqualinkRobotActivity.ERROR,
        )

    def test_capabilities(self):
        r = _robot()
        self.assertTrue(r.supports_start)
        self.assertTrue(r.supports_stop)
        self.assertTrue(r.supports_pause)
        self.assertTrue(r.supports_return)
        self.assertTrue(r.supports_fan_speed)
        self.assertFalse(r.supports_clean_spot)
        self.assertFalse(r.supports_locate)

    def test_fan_speed_reads_cycle(self):
        self.assertEqual(_robot({"cycle": 3}).fan_speed, "floor_and_walls")

    def test_fan_speed_none_when_absent(self):
        self.assertIsNone(_robot({}).fan_speed)

    def test_fan_speed_list(self):
        self.assertEqual(_robot().fan_speed_list, ["floor", "floor_and_walls"])


class TestCyclonextRobotCommands(unittest.IsolatedAsyncioTestCase):
    async def test_start_delegates(self):
        r = _robot()
        r.system.start_cleaning = AsyncMock()
        await r.start()
        cast(AsyncMock, r.system.start_cleaning).assert_awaited_once_with()

    async def test_stop_delegates(self):
        r = _robot()
        r.system.stop_cleaning = AsyncMock()
        await r.stop()
        cast(AsyncMock, r.system.stop_cleaning).assert_awaited_once_with()

    async def test_pause_delegates(self):
        r = _robot()
        r.system.pause_cleaning = AsyncMock()
        await r.pause()
        cast(AsyncMock, r.system.pause_cleaning).assert_awaited_once_with()

    async def test_return_aliases_stop(self):
        # Wired robot has no dock: return_to_base maps to the stop frame.
        r = _robot()
        r.system.stop_cleaning = AsyncMock()
        await r.return_to_base()
        cast(AsyncMock, r.system.stop_cleaning).assert_awaited_once_with()

    async def test_set_fan_speed_maps_to_cycle(self):
        from iaqualink.systems.cyclonext.const import CYCLE_FLOOR

        r = _robot()
        r.system.set_cycle = AsyncMock()
        await r.set_fan_speed("floor")
        cast(AsyncMock, r.system.set_cycle).assert_awaited_once_with(
            CYCLE_FLOOR
        )

    async def test_set_fan_speed_unknown_raises(self):
        from iaqualink.exception import AqualinkInvalidParameterException

        r = _robot()
        r.system.set_cycle = AsyncMock()
        with self.assertRaises(AqualinkInvalidParameterException):
            await r.set_fan_speed("turbo")
        cast(AsyncMock, r.system.set_cycle).assert_not_awaited()

    async def test_set_fan_speed_private_guard_rejects_unknown(self):
        from iaqualink.exception import AqualinkInvalidParameterException

        r = _robot()
        r.system.set_cycle = AsyncMock()
        with self.assertRaises(AqualinkInvalidParameterException):
            await r._set_fan_speed("turbo")
        cast(AsyncMock, r.system.set_cycle).assert_not_awaited()


# ── Cyclonext sensor HA metadata (parity with cyclobat T33) ──────────────────


def _sensor(name: str, state: object) -> CyclonextSensor:
    system = make_system()
    # Routes to CyclonextSensor / CyclonextErrorSensor / CyclonextBinarySensor
    # at runtime; cast to the sensor subclass so ty resolves the HA-metadata
    # props the tests assert on (subclasses share device_class/entity_category).
    return cast(
        CyclonextSensor,
        CyclonextDevice.from_data(system, _device_data(name, state)),
    )


class TestCyclonextSensorMetadata(unittest.TestCase):
    def test_time_remaining_sec(self):
        s = _sensor("time_remaining_sec", "600")
        self.assertEqual(s.device_class, "duration")
        self.assertEqual(s.unit_of_measurement, "s")
        self.assertEqual(s.state_class, "measurement")
        self.assertEqual(s.value, 600)
        self.assertIsNone(s.entity_category)

    def test_stepper(self):
        s = _sensor("stepper", "30")
        self.assertEqual(s.device_class, "duration")
        self.assertEqual(s.unit_of_measurement, "min")
        self.assertEqual(s.value, 30)

    def test_error_code_numeric_and_diagnostic(self):
        s = _sensor("error_code", "0")
        self.assertIsNone(s.device_class)
        self.assertEqual(s.value, 0)
        self.assertEqual(s.entity_category, "diagnostic")

    def test_firmware_and_identifier_diagnostic(self):
        for name in ("control_box_vr", "model_number", "ebox_sn"):
            self.assertEqual(_sensor(name, "x").entity_category, "diagnostic")

    def test_plain_state_sensor_no_metadata(self):
        s = _sensor("mode", "1")
        self.assertIsNone(s.device_class)
        self.assertIsNone(s.state_class)
        self.assertIsNone(s.entity_category)
        self.assertEqual(s.value, "1")

    def test_value_unparseable_returns_none(self):
        self.assertIsNone(_sensor("time_remaining_sec", "n/a").value)


class TestCyclonextBinarySensorMetadata(unittest.TestCase):
    def test_running_device_class_and_diagnostic(self):
        s = _sensor("running", 1)
        self.assertEqual(s.device_class, "running")
        self.assertEqual(s.entity_category, "diagnostic")


if __name__ == "__main__":
    unittest.main()
