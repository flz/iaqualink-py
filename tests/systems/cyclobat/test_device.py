from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from iaqualink.device import AqualinkBinarySensor, AqualinkSensor


class TestCyclobatDeviceFromData(unittest.TestCase):
    def setUp(self) -> None:
        self.system = MagicMock()
        self.system.serial = "SN42"

    def _from_data(self, name: str, state: object) -> object:
        from iaqualink.systems.cyclobat.device import CyclobatDevice

        return CyclobatDevice.from_data(
            self.system, {"name": name, "state": state}
        )

    # from_data routing
    def test_from_data_running_is_binary_sensor(self) -> None:
        from iaqualink.systems.cyclobat.device import CyclobatBinarySensor

        dev = self._from_data("running", 1)
        self.assertIsInstance(dev, CyclobatBinarySensor)
        self.assertIsInstance(dev, AqualinkBinarySensor)

    def test_from_data_returning_is_binary_sensor(self) -> None:
        from iaqualink.systems.cyclobat.device import CyclobatBinarySensor

        dev = self._from_data("returning", 0)
        self.assertIsInstance(dev, CyclobatBinarySensor)

    def test_from_data_battery_percentage_is_sensor(self) -> None:
        from iaqualink.systems.cyclobat.device import CyclobatSensor

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
        from iaqualink.systems.cyclobat.device import CyclobatBinarySensor

        dev = CyclobatBinarySensor(self.system, {"name": "running", "state": 1})
        self.assertEqual(dev.model, "BinarySensor")

    def test_model_sensor_strips_prefix(self) -> None:
        from iaqualink.systems.cyclobat.device import CyclobatSensor

        dev = CyclobatSensor(
            self.system, {"name": "battery_percentage", "state": 87}
        )
        self.assertEqual(dev.model, "Sensor")

    # is_on
    def test_binary_sensor_is_on_true(self) -> None:
        from iaqualink.systems.cyclobat.device import CyclobatBinarySensor

        dev = CyclobatBinarySensor(self.system, {"name": "running", "state": 1})
        self.assertTrue(dev.is_on)

    def test_binary_sensor_is_on_false(self) -> None:
        from iaqualink.systems.cyclobat.device import CyclobatBinarySensor

        dev = CyclobatBinarySensor(self.system, {"name": "running", "state": 0})
        self.assertFalse(dev.is_on)

    # value
    def test_sensor_value_stringified(self) -> None:
        from iaqualink.systems.cyclobat.device import CyclobatSensor

        dev = CyclobatSensor(
            self.system, {"name": "battery_percentage", "state": 87}
        )
        self.assertEqual(dev.value, "87")


if __name__ == "__main__":
    unittest.main()
