from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from iaqualink.systems.cyclonext.device import (
    CyclonextAttributeSensor,
    CyclonextBinarySensor,
    CyclonextDevice,
    CyclonextErrorSensor,
)


class TestCyclonextDevice(unittest.IsolatedAsyncioTestCase):
    def _make(self, name: str, state: object) -> CyclonextDevice:
        system = MagicMock()
        return CyclonextDevice.from_data(system, {"name": name, "state": state})

    def test_from_data_dispatch(self) -> None:
        assert isinstance(self._make("running", 1), CyclonextBinarySensor)
        assert isinstance(self._make("error_code", 0), CyclonextErrorSensor)
        assert isinstance(self._make("mode", 1), CyclonextAttributeSensor)

    def test_label_pretty(self) -> None:
        d = self._make("control_box_vr", "V21C27")
        assert d.label == "Control Box Vr"

    def test_state_str_cast(self) -> None:
        d = self._make("totRunTime", 15041)
        assert d.state == "15041"

    def test_binary_sensor_is_on(self) -> None:
        on = self._make("running", 1)
        assert isinstance(on, CyclonextBinarySensor)
        assert on.is_on is True
        off = self._make("running", 0)
        assert isinstance(off, CyclonextBinarySensor)
        assert off.is_on is False

    def test_manufacturer_zodiac(self) -> None:
        d = self._make("mode", 1)
        assert d.manufacturer == "Zodiac"
