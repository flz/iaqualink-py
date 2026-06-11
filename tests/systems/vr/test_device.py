from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, MagicMock

from iaqualink.device import AqualinkBinarySensor, AqualinkSensor


class TestVrDeviceFromData(unittest.TestCase):
    def setUp(self) -> None:
        self.system = MagicMock()
        self.system.serial = "SN42"

    def _from_data(self, name: str, state: object) -> object:
        from iaqualink.systems.vr.device import VrDevice

        return VrDevice.from_data(self.system, {"name": name, "state": state})

    # from_data routing
    def test_from_data_running_is_binary_sensor(self) -> None:
        from iaqualink.systems.vr.device import VrBinarySensor

        dev = self._from_data("running", 1)
        self.assertIsInstance(dev, VrBinarySensor)
        self.assertIsInstance(dev, AqualinkBinarySensor)

    def test_from_data_returning_is_binary_sensor(self) -> None:
        from iaqualink.systems.vr.device import VrBinarySensor

        dev = self._from_data("returning", 0)
        self.assertIsInstance(dev, VrBinarySensor)

    def test_from_data_error_state_is_error_sensor(self) -> None:
        from iaqualink.systems.vr.device import VrErrorSensor

        dev = self._from_data("error_state", 0)
        self.assertIsInstance(dev, VrErrorSensor)
        self.assertIsInstance(dev, AqualinkSensor)

    def test_from_data_battery_is_sensor(self) -> None:
        from iaqualink.systems.vr.device import VrSensor

        dev = self._from_data("battery", 80)
        self.assertIsInstance(dev, VrSensor)
        self.assertIsInstance(dev, AqualinkSensor)

    # label
    def test_label_underscores_to_title_case(self) -> None:
        dev = self._from_data("cycle_start_time", 0)
        self.assertEqual(dev.label, "Cycle Start Time")

    def test_label_single_word(self) -> None:
        dev = self._from_data("running", 1)
        self.assertEqual(dev.label, "Running")

    # manufacturer
    def test_manufacturer_zodiac_sensor(self) -> None:
        dev = self._from_data("battery", 80)
        self.assertEqual(dev.manufacturer, "Zodiac")

    def test_manufacturer_zodiac_binary(self) -> None:
        dev = self._from_data("running", 0)
        self.assertEqual(dev.manufacturer, "Zodiac")

    def test_manufacturer_zodiac_error(self) -> None:
        dev = self._from_data("error_state", 0)
        self.assertEqual(dev.manufacturer, "Zodiac")

    # model
    def test_model_binary_sensor_strips_prefix(self) -> None:
        from iaqualink.systems.vr.device import VrBinarySensor

        dev = VrBinarySensor(self.system, {"name": "running", "state": 1})
        self.assertEqual(dev.model, "BinarySensor")

    def test_model_error_sensor_strips_prefix(self) -> None:
        from iaqualink.systems.vr.device import VrErrorSensor

        dev = VrErrorSensor(self.system, {"name": "error_state", "state": 0})
        self.assertEqual(dev.model, "ErrorSensor")

    def test_model_sensor_strips_prefix(self) -> None:
        from iaqualink.systems.vr.device import VrSensor

        dev = VrSensor(self.system, {"name": "battery", "state": 80})
        self.assertEqual(dev.model, "Sensor")

    # is_on
    def test_binary_sensor_is_on_true(self) -> None:
        from iaqualink.systems.vr.device import VrBinarySensor

        dev = VrBinarySensor(self.system, {"name": "running", "state": 1})
        self.assertTrue(dev.is_on)

    def test_binary_sensor_is_on_false(self) -> None:
        from iaqualink.systems.vr.device import VrBinarySensor

        dev = VrBinarySensor(self.system, {"name": "running", "state": 0})
        self.assertFalse(dev.is_on)

    # value
    def test_sensor_value_stringified(self) -> None:
        from iaqualink.systems.vr.device import VrSensor

        dev = VrSensor(self.system, {"name": "battery", "state": 42})
        self.assertEqual(dev.value, "42")

    def test_error_sensor_value_numeric(self) -> None:
        from iaqualink.systems.vr.device import VrErrorSensor

        dev = VrErrorSensor(self.system, {"name": "error_state", "state": 5})
        self.assertEqual(dev.value, 5)


# ── VrRobot (HA vacuum) ──────────────────────────────────────────────────────


def _robot(robot_state=None):
    from iaqualink.systems.vr.device import VrRobot

    system = MagicMock()
    system.serial = "SN1"
    system._robot_state = robot_state if robot_state is not None else {}
    return VrRobot(system, {"name": "robot", "state": 0})


class TestVrRobot(unittest.TestCase):
    def test_from_data_robot_is_robot(self):
        from iaqualink.device import AqualinkVacuum
        from iaqualink.systems.vr.device import VrDevice, VrRobot

        system = MagicMock()
        system.serial = "SN1"
        dev = VrDevice.from_data(system, {"name": "robot", "state": 1})
        self.assertIsInstance(dev, VrRobot)
        self.assertIsInstance(dev, AqualinkVacuum)

    def test_activity_states(self):
        from iaqualink.enums import AqualinkRobotActivity as A

        self.assertIs(_robot({"state": 0}).activity, A.IDLE)
        self.assertIs(_robot({"state": 1}).activity, A.CLEANING)
        self.assertIs(_robot({"state": 2}).activity, A.PAUSED)
        self.assertIs(_robot({"state": 3}).activity, A.RETURNING)

    def test_activity_error_overrides_state(self):
        from iaqualink.enums import AqualinkRobotActivity as A

        self.assertIs(_robot({"state": 1, "errorState": 4}).activity, A.ERROR)

    def test_capabilities(self):
        r = _robot()
        self.assertTrue(r.supports_start)
        self.assertTrue(r.supports_stop)
        self.assertTrue(r.supports_pause)
        self.assertTrue(r.supports_return)
        self.assertTrue(r.supports_fan_speed)
        self.assertFalse(r.supports_clean_spot)
        self.assertFalse(r.supports_locate)

    def test_fan_speed_reads_prcyc(self):
        self.assertEqual(
            _robot({"prCyc": 2}).fan_speed, "smart_floor_and_walls"
        )

    def test_fan_speed_none_when_absent(self):
        self.assertIsNone(_robot({}).fan_speed)

    def test_fan_speed_list(self):
        self.assertEqual(
            _robot().fan_speed_list,
            [
                "wall_only",
                "floor_only",
                "smart_floor_and_walls",
                "floor_and_walls",
            ],
        )


class TestVrRobotCommands(unittest.IsolatedAsyncioTestCase):
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

    async def test_return_delegates(self):
        # vr has a real RETURNING state + return_to_base command (no alias).
        r = _robot()
        r.system.return_to_base = AsyncMock()
        await r.return_to_base()
        r.system.return_to_base.assert_awaited_once_with()

    async def test_set_fan_speed_maps_to_cycle(self):
        from iaqualink.systems.vr.const import CYCLE_FLOOR_ONLY

        r = _robot()
        r.system.set_cycle = AsyncMock()
        await r.set_fan_speed("floor_only")
        r.system.set_cycle.assert_awaited_once_with(CYCLE_FLOOR_ONLY)

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


# ── Vr sensor HA metadata (parity with cyclobat/cyclonext) ───────────────────


def _sensor(name, state):
    from iaqualink.systems.vr.device import VrDevice

    system = MagicMock()
    system.serial = "SN1"
    return VrDevice.from_data(system, {"name": name, "state": state})


class TestVrSensorMetadata(unittest.TestCase):
    def test_temperature(self):
        s = _sensor("temperature", "25")
        self.assertEqual(s.device_class, "temperature")
        self.assertEqual(s.unit_of_measurement, "°C")
        self.assertEqual(s.state_class, "measurement")
        self.assertEqual(s.value, 25)

    def test_time_remaining_sec(self):
        s = _sensor("time_remaining_sec", "600")
        self.assertEqual(s.device_class, "duration")
        self.assertEqual(s.unit_of_measurement, "s")
        self.assertEqual(s.value, 600)

    def test_stepper(self):
        s = _sensor("stepper", "30")
        self.assertEqual(s.device_class, "duration")
        self.assertEqual(s.unit_of_measurement, "min")
        self.assertEqual(s.value, 30)

    def test_error_state_numeric_and_diagnostic(self):
        s = _sensor("error_state", "0")
        self.assertIsNone(s.device_class)
        self.assertEqual(s.value, 0)
        self.assertEqual(s.entity_category, "diagnostic")

    def test_firmware_and_identifier_diagnostic(self):
        for name in ("vr", "model_number"):
            self.assertEqual(_sensor(name, "x").entity_category, "diagnostic")

    def test_plain_state_sensor_no_metadata(self):
        s = _sensor("state", "1")
        self.assertIsNone(s.device_class)
        self.assertIsNone(s.entity_category)
        self.assertEqual(s.value, "1")


class TestVrBinarySensorMetadata(unittest.TestCase):
    def test_running_device_class_and_diagnostic(self):
        s = _sensor("running", 1)
        self.assertEqual(s.device_class, "running")
        self.assertEqual(s.entity_category, "diagnostic")

    def test_returning_diagnostic(self):
        self.assertEqual(_sensor("returning", 0).entity_category, "diagnostic")


if __name__ == "__main__":
    unittest.main()
