from __future__ import annotations

import unittest
from unittest.mock import MagicMock

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

    def test_error_sensor_value_stringified(self) -> None:
        from iaqualink.systems.vr.device import VrErrorSensor

        dev = VrErrorSensor(self.system, {"name": "error_state", "state": 5})
        self.assertEqual(dev.value, "5")


if __name__ == "__main__":
    unittest.main()
