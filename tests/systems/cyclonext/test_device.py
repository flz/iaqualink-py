from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from iaqualink.device import AqualinkBinarySensor, AqualinkSensor


class TestCyclonextDeviceFromData(unittest.TestCase):
    def setUp(self) -> None:
        self.system = MagicMock()
        self.system.serial = "SN42"

    def _from_data(self, name: str, state: object) -> object:
        from iaqualink.systems.cyclonext.device import CyclonextDevice

        return CyclonextDevice.from_data(
            self.system, {"name": name, "state": state}
        )

    # from_data routing
    def test_from_data_running_is_binary_sensor(self) -> None:
        from iaqualink.systems.cyclonext.device import CyclonextBinarySensor

        dev = self._from_data("running", 1)
        self.assertIsInstance(dev, CyclonextBinarySensor)
        self.assertIsInstance(dev, AqualinkBinarySensor)

    def test_from_data_error_code_is_error_sensor(self) -> None:
        from iaqualink.systems.cyclonext.device import CyclonextErrorSensor

        dev = self._from_data("error_code", 0)
        self.assertIsInstance(dev, CyclonextErrorSensor)
        self.assertIsInstance(dev, AqualinkSensor)

    def test_from_data_mode_is_sensor(self) -> None:
        from iaqualink.systems.cyclonext.device import CyclonextSensor

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
        from iaqualink.systems.cyclonext.device import CyclonextBinarySensor

        dev = CyclonextBinarySensor(
            self.system, {"name": "running", "state": 1}
        )
        self.assertEqual(dev.model, "BinarySensor")

    def test_model_error_sensor_strips_prefix(self) -> None:
        from iaqualink.systems.cyclonext.device import CyclonextErrorSensor

        dev = CyclonextErrorSensor(
            self.system, {"name": "error_code", "state": 0}
        )
        self.assertEqual(dev.model, "ErrorSensor")

    def test_model_sensor_strips_prefix(self) -> None:
        from iaqualink.systems.cyclonext.device import CyclonextSensor

        dev = CyclonextSensor(self.system, {"name": "mode", "state": 1})
        self.assertEqual(dev.model, "Sensor")

    # is_on
    def test_binary_sensor_is_on_true(self) -> None:
        from iaqualink.systems.cyclonext.device import CyclonextBinarySensor

        dev = CyclonextBinarySensor(
            self.system, {"name": "running", "state": 1}
        )
        self.assertTrue(dev.is_on)

    def test_binary_sensor_is_on_false(self) -> None:
        from iaqualink.systems.cyclonext.device import CyclonextBinarySensor

        dev = CyclonextBinarySensor(
            self.system, {"name": "running", "state": 0}
        )
        self.assertFalse(dev.is_on)

    # value
    def test_sensor_value_stringified(self) -> None:
        from iaqualink.systems.cyclonext.device import CyclonextSensor

        dev = CyclonextSensor(self.system, {"name": "mode", "state": "v1.2.3"})
        self.assertEqual(dev.value, "v1.2.3")

    def test_error_sensor_value_stringified(self) -> None:
        from iaqualink.systems.cyclonext.device import CyclonextErrorSensor

        dev = CyclonextErrorSensor(
            self.system, {"name": "error_code", "state": 5}
        )
        self.assertEqual(dev.value, "5")


# ── CyclonextRobot (HA vacuum) ───────────────────────────────────────────────


def _robot(robot_state=None):
    from iaqualink.systems.cyclonext.device import CyclonextRobot

    system = MagicMock()
    system.serial = "SN1"
    system._robot_state = robot_state if robot_state is not None else {}
    return CyclonextRobot(system, {"name": "robot", "state": 0})


class TestCyclonextRobot(unittest.TestCase):
    def test_from_data_robot_is_robot(self):
        from iaqualink.device import AqualinkRobot
        from iaqualink.systems.cyclonext.device import (
            CyclonextDevice,
            CyclonextRobot,
        )

        system = MagicMock()
        system.serial = "SN1"
        dev = CyclonextDevice.from_data(system, {"name": "robot", "state": 1})
        self.assertIsInstance(dev, CyclonextRobot)
        self.assertIsInstance(dev, AqualinkRobot)

    def test_activity_cleaning(self):
        from iaqualink.device import AqualinkRobotActivity

        self.assertIs(
            _robot({"mode": 1}).activity, AqualinkRobotActivity.CLEANING
        )

    def test_activity_remote_is_paused(self):
        from iaqualink.device import AqualinkRobotActivity

        self.assertIs(
            _robot({"mode": 2}).activity, AqualinkRobotActivity.PAUSED
        )

    def test_activity_lift_is_idle(self):
        from iaqualink.device import AqualinkRobotActivity

        self.assertIs(_robot({"mode": 3}).activity, AqualinkRobotActivity.IDLE)

    def test_activity_stopped_is_idle(self):
        from iaqualink.device import AqualinkRobotActivity

        self.assertIs(_robot({"mode": 0}).activity, AqualinkRobotActivity.IDLE)

    def test_activity_error_overrides_mode(self):
        from iaqualink.device import AqualinkRobotActivity

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
        r.system.start_cleaning.assert_awaited_once_with()

    async def test_stop_delegates(self):
        r = _robot()
        r.system.stop_cleaning = AsyncMock()
        await r.stop()
        r.system.stop_cleaning.assert_awaited_once_with()

    async def test_pause_delegates(self):
        r = _robot()
        r.system.pause_cleaning = AsyncMock()
        await r.pause()
        r.system.pause_cleaning.assert_awaited_once_with()

    async def test_return_aliases_stop(self):
        # Wired robot has no dock: return_to_base maps to the stop frame.
        r = _robot()
        r.system.stop_cleaning = AsyncMock()
        await r.return_to_base()
        r.system.stop_cleaning.assert_awaited_once_with()

    async def test_set_fan_speed_maps_to_cycle(self):
        from iaqualink.systems.cyclonext.const import CYCLE_FLOOR

        r = _robot()
        r.system.set_cycle = AsyncMock()
        await r.set_fan_speed("floor")
        r.system.set_cycle.assert_awaited_once_with(CYCLE_FLOOR)

    async def test_set_fan_speed_unknown_raises(self):
        from iaqualink.exception import AqualinkInvalidParameterException

        r = _robot()
        r.system.set_cycle = AsyncMock()
        with self.assertRaises(AqualinkInvalidParameterException):
            await r.set_fan_speed("turbo")
        r.system.set_cycle.assert_not_awaited()

    async def test_set_fan_speed_private_guard_rejects_unknown(self):
        from iaqualink.exception import AqualinkInvalidParameterException

        r = _robot()
        r.system.set_cycle = AsyncMock()
        with self.assertRaises(AqualinkInvalidParameterException):
            await r._set_fan_speed("turbo")
        r.system.set_cycle.assert_not_awaited()


# ── Cyclonext sensor HA metadata (parity with cyclobat T33) ──────────────────


def _sensor(name, state):
    from iaqualink.systems.cyclonext.device import CyclonextDevice

    system = MagicMock()
    system.serial = "SN1"
    return CyclonextDevice.from_data(system, {"name": name, "state": state})


class TestCyclonextSensorMetadata(unittest.TestCase):
    def test_time_remaining_sec(self):
        s = _sensor("time_remaining_sec", "600")
        self.assertEqual(s.device_class, "duration")
        self.assertEqual(s.unit_of_measurement, "s")
        self.assertEqual(s.state_class, "measurement")
        self.assertEqual(s.native_value, 600)
        self.assertIsNone(s.entity_category)

    def test_stepper(self):
        s = _sensor("stepper", "30")
        self.assertEqual(s.device_class, "duration")
        self.assertEqual(s.unit_of_measurement, "min")
        self.assertEqual(s.native_value, 30)

    def test_error_code_numeric_and_diagnostic(self):
        s = _sensor("error_code", "0")
        self.assertIsNone(s.device_class)
        self.assertEqual(s.native_value, 0)
        self.assertEqual(s.entity_category, "diagnostic")

    def test_firmware_and_identifier_diagnostic(self):
        for name in ("control_box_vr", "model_number", "ebox_sn"):
            self.assertEqual(_sensor(name, "x").entity_category, "diagnostic")

    def test_plain_state_sensor_no_metadata(self):
        s = _sensor("mode", "1")
        self.assertIsNone(s.device_class)
        self.assertIsNone(s.state_class)
        self.assertIsNone(s.entity_category)
        self.assertEqual(s.native_value, "1")

    def test_native_value_unparseable_returns_none(self):
        self.assertIsNone(_sensor("time_remaining_sec", "n/a").native_value)


class TestCyclonextBinarySensorMetadata(unittest.TestCase):
    def test_running_device_class_and_diagnostic(self):
        s = _sensor("running", 1)
        self.assertEqual(s.device_class, "running")
        self.assertEqual(s.entity_category, "diagnostic")


if __name__ == "__main__":
    unittest.main()
