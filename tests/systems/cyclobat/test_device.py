from __future__ import annotations

import unittest
from typing import Any, cast
from unittest.mock import AsyncMock

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkSensor,
)
from iaqualink.systems.cyclobat.device import (
    CyclobatBinarySensor,
    CyclobatDevice,
    CyclobatRobot,
    CyclobatSensor,
)

from .factories import make_system


def _device_data(name: str, state: object) -> dict[str, Any]:
    """Build raw device data; ``dict[str, Any]`` satisfies ``DeviceData``."""
    return {"name": name, "state": state}


class TestCyclobatDeviceFromData(unittest.TestCase):
    def setUp(self) -> None:
        self.system = make_system()

    def _from_data(self, name: str, state: object) -> AqualinkDevice:
        return CyclobatDevice.from_data(self.system, _device_data(name, state))

    # from_data routing
    def test_from_data_running_is_binary_sensor(self) -> None:
        dev = self._from_data("running", 1)
        self.assertIsInstance(dev, CyclobatBinarySensor)
        self.assertIsInstance(dev, AqualinkBinarySensor)

    def test_from_data_returning_is_binary_sensor(self) -> None:
        dev = self._from_data("returning", 0)
        self.assertIsInstance(dev, CyclobatBinarySensor)

    def test_from_data_battery_percentage_is_sensor(self) -> None:
        dev = self._from_data("battery_percentage", 87)
        self.assertIsInstance(dev, CyclobatSensor)
        self.assertIsInstance(dev, AqualinkSensor)

    # label
    def test_label_underscores_to_title_case(self) -> None:
        dev = self._from_data("battery_percentage", 87)
        self.assertEqual(dev.label, "Battery Percentage")

    def test_label_single_word(self) -> None:
        dev = self._from_data("running", 1)
        self.assertEqual(dev.label, "Running")

    # manufacturer
    def test_manufacturer_zodiac(self) -> None:
        dev = self._from_data("battery_percentage", 50)
        self.assertEqual(dev.manufacturer, "Zodiac")

    def test_manufacturer_binary_zodiac(self) -> None:
        dev = self._from_data("running", 0)
        self.assertEqual(dev.manufacturer, "Zodiac")

    # model
    def test_model_binary_sensor_strips_prefix(self) -> None:
        dev = CyclobatBinarySensor(self.system, _device_data("running", 1))
        self.assertEqual(dev.model, "BinarySensor")

    def test_model_sensor_strips_prefix(self) -> None:
        dev = CyclobatSensor(
            self.system, _device_data("battery_percentage", 87)
        )
        self.assertEqual(dev.model, "Sensor")

    # is_on
    def test_binary_sensor_is_on_true(self) -> None:
        dev = CyclobatBinarySensor(self.system, _device_data("running", 1))
        self.assertTrue(dev.is_on)

    def test_binary_sensor_is_on_false(self) -> None:
        dev = CyclobatBinarySensor(self.system, _device_data("running", 0))
        self.assertFalse(dev.is_on)

    # value
    def test_sensor_value_stringified(self) -> None:
        dev = CyclobatSensor(
            self.system, _device_data("battery_percentage", 87)
        )
        self.assertEqual(dev.value, 87)


# ── CyclobatRobot (HA vacuum) ────────────────────────────────────────────────


def _robot(
    main: dict[str, Any] | None = None,
    battery: dict[str, Any] | None = None,
) -> CyclobatRobot:
    system = make_system()
    system._robot_state = {
        "main": main if main is not None else {},
        "battery": battery if battery is not None else {},
    }
    return CyclobatRobot(system, _device_data("robot", 0))


class TestCyclobatRobot(unittest.TestCase):
    def test_from_data_robot_is_robot(self):
        from iaqualink.device import AqualinkVacuum

        system = make_system()
        dev = CyclobatDevice.from_data(system, _device_data("robot", 1))
        self.assertIsInstance(dev, CyclobatRobot)
        self.assertIsInstance(dev, AqualinkVacuum)

    def test_activity_cleaning(self):
        from iaqualink.enums import AqualinkRobotActivity

        self.assertIs(
            _robot({"state": 1}).activity, AqualinkRobotActivity.CLEANING
        )

    def test_activity_returning(self):
        from iaqualink.enums import AqualinkRobotActivity

        self.assertIs(
            _robot({"state": 3}).activity, AqualinkRobotActivity.RETURNING
        )

    def test_activity_docked_when_stopped(self):
        from iaqualink.enums import AqualinkRobotActivity

        self.assertIs(
            _robot({"state": 0}).activity, AqualinkRobotActivity.DOCKED
        )

    def test_activity_error_overrides_state(self):
        from iaqualink.enums import AqualinkRobotActivity

        self.assertIs(
            _robot({"state": 1, "error": 7}).activity,
            AqualinkRobotActivity.ERROR,
        )

    def test_capabilities(self):
        r = _robot()
        self.assertTrue(r.supports_start)
        self.assertTrue(r.supports_stop)
        self.assertTrue(r.supports_return)
        self.assertTrue(r.supports_fan_speed)
        self.assertFalse(r.supports_pause)
        self.assertFalse(r.supports_clean_spot)
        self.assertFalse(r.supports_locate)
        self.assertFalse(r.supports_battery)

    def test_fan_speed_reads_mode(self):
        self.assertEqual(_robot({"mode": 3}).fan_speed, "waterline")

    def test_fan_speed_none_when_absent(self):
        self.assertIsNone(_robot({}).fan_speed)

    def test_fan_speed_list(self):
        self.assertEqual(
            _robot().fan_speed_list,
            ["floor", "floor_and_walls", "smart", "waterline"],
        )

    def test_battery_level_reads_user_charge_perc(self):
        r = _robot(battery={"userChargePerc": 87})
        self.assertEqual(r.battery_level, 87)
        self.assertTrue(r.supports_battery)

    def test_battery_level_none_when_absent(self):
        r = _robot()
        self.assertIsNone(r.battery_level)
        self.assertFalse(r.supports_battery)


class TestCyclobatRobotCommands(unittest.IsolatedAsyncioTestCase):
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

    async def test_set_fan_speed_maps_to_mode(self):
        from iaqualink.systems.cyclobat.const import CYCLE_FLOOR

        r = _robot()
        r.system.set_cleaning_mode = AsyncMock()
        await r.set_fan_speed("floor")
        r.system.set_cleaning_mode.assert_awaited_once_with(CYCLE_FLOOR)

    async def test_set_fan_speed_unknown_raises(self):
        from iaqualink.exception import AqualinkInvalidParameterException

        r = _robot()
        r.system.set_cleaning_mode = AsyncMock()
        with self.assertRaises(AqualinkInvalidParameterException):
            await r.set_fan_speed("turbo")
        r.system.set_cleaning_mode.assert_not_awaited()

    async def test_set_fan_speed_private_guard_rejects_unknown(self):
        # Defensive: a direct _set_fan_speed call with an unmapped name raises
        # AqualinkInvalidParameterException, not a bare KeyError.
        from iaqualink.exception import AqualinkInvalidParameterException

        r = _robot()
        r.system.set_cleaning_mode = AsyncMock()
        with self.assertRaises(AqualinkInvalidParameterException):
            await r._set_fan_speed("turbo")
        r.system.set_cleaning_mode.assert_not_awaited()


# ── CyclobatSensor / BinarySensor HA metadata ────────────────────────────────


def _sensor(name: str, state: object) -> CyclobatSensor:
    system = make_system()
    # Routes to CyclobatSensor or CyclobatBinarySensor at runtime; cast to the
    # sensor subclass so ty resolves the HA-metadata props the tests assert on
    # (both subclasses share device_class/entity_category).
    return cast(
        CyclobatSensor,
        CyclobatDevice.from_data(system, _device_data(name, state)),
    )


class TestCyclobatSensorMetadata(unittest.TestCase):
    def test_battery_percentage(self):
        s = _sensor("battery_percentage", "87")
        self.assertEqual(s.device_class, "battery")
        self.assertEqual(s.unit_of_measurement, "%")
        self.assertEqual(s.state_class, "measurement")
        self.assertEqual(s.value, 87)

    def test_temperature(self):
        s = _sensor("temperature", "28.5")
        self.assertEqual(s.device_class, "temperature")
        self.assertEqual(s.unit_of_measurement, "°C")
        self.assertEqual(s.state_class, "measurement")
        self.assertEqual(s.value, 28.5)

    def test_time_remaining_sec(self):
        s = _sensor("time_remaining_sec", "600")
        self.assertEqual(s.device_class, "duration")
        self.assertEqual(s.unit_of_measurement, "s")
        self.assertEqual(s.state_class, "measurement")
        self.assertEqual(s.value, 600)

    def test_cycle_duration(self):
        s = _sensor("floor_duration", "120")
        self.assertEqual(s.device_class, "duration")
        self.assertEqual(s.unit_of_measurement, "min")
        self.assertEqual(s.value, 120)

    def test_total_runtime(self):
        s = _sensor("total_runtime", "4200")
        self.assertIsNone(s.device_class)
        self.assertEqual(s.unit_of_measurement, "min")
        self.assertEqual(s.state_class, "total_increasing")
        self.assertEqual(s.value, 4200)

    def test_plain_sensor_has_no_metadata(self):
        s = _sensor("vr", "1.2.3")
        self.assertIsNone(s.device_class)
        self.assertIsNone(s.state_class)
        self.assertIsNone(s.unit_of_measurement)
        self.assertEqual(s.value, "1.2.3")

    def test_native_value_non_numeric_meta_returns_str(self):
        # battery_state isn't in the numeric metadata set.
        s = _sensor("battery_state", "charging")
        self.assertEqual(s.value, "charging")

    def test_native_value_unparseable_returns_none(self):
        s = _sensor("battery_percentage", "n/a")
        self.assertIsNone(s.value)

    def test_regular_sensor_no_entity_category(self):
        self.assertIsNone(_sensor("battery_percentage", "87").entity_category)


class TestCyclobatBinarySensorMetadata(unittest.TestCase):
    def test_running_device_class(self):
        self.assertEqual(_sensor("running", 1).device_class, "running")

    def test_returning_has_no_device_class(self):
        self.assertIsNone(_sensor("returning", 0).device_class)

    def test_running_is_diagnostic(self):
        self.assertEqual(_sensor("running", 1).entity_category, "diagnostic")

    def test_returning_is_diagnostic(self):
        self.assertEqual(_sensor("returning", 0).entity_category, "diagnostic")


if __name__ == "__main__":
    unittest.main()
