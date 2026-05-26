from __future__ import annotations

import unittest
from unittest.mock import MagicMock

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


if __name__ == "__main__":
    unittest.main()
