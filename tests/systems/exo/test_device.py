from __future__ import annotations

import copy
import unittest
from unittest.mock import AsyncMock, MagicMock

import pytest

from iaqualink.systems.exo.device import (
    ExoAttributeSensor,
    ExoAttributeToggle,
    ExoAuxToggle,
    ExoDevice,
    ExoSensor,
    ExoThermostat,
    ExoToggle,
)

from ...common import async_noop


class TestExoDevice(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        system = MagicMock()
        data = {"name": "Test Device"}
        self.obj = ExoDevice(system, data)

    def test_equal(self) -> None:
        assert self.obj == self.obj

    def test_not_equal(self) -> None:
        obj2 = copy.deepcopy(self.obj)
        obj2.data["name"] = "Test Device 2"
        assert self.obj != obj2

    def test_not_equal_different_type(self) -> None:
        assert (self.obj == {}) is False


class TestExoSensor(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.system = system = MagicMock()
        data = {
            "name": "sns_1",
            "sensor_type": "Foo",
            "value": 42,
            "state": 1,
        }
        self.obj = ExoDevice.from_data(system, data)

    def test_from_data(self) -> None:
        assert isinstance(self.obj, ExoSensor)

    def test_attributes(self) -> None:
        assert self.obj.name == "foo"
        assert self.obj.label == "Foo"
        assert self.obj.manufacturer == "Zodiac"
        assert self.obj.model == "Sensor"
        assert self.obj.state == "42"

    def test_state_unavailable(self) -> None:
        self.obj.data["state"] = 0
        assert self.obj.state == ""


class TestExoAttributeSensor(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.system = system = MagicMock()
        data = {
            "name": "foo_bar",
            "state": 42,
        }
        self.obj = ExoDevice.from_data(system, data)

    def test_from_data(self) -> None:
        assert isinstance(self.obj, ExoAttributeSensor)

    def test_attributes(self) -> None:
        assert self.obj.name == "foo_bar"
        assert self.obj.label == "Foo Bar"
        assert self.obj.manufacturer == "Zodiac"
        assert self.obj.model == "AttributeSensor"
        assert self.obj.state == "42"


class TestExoToggle(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.system = system = MagicMock()
        data = {
            "name": "toggle",
            "state": 0,
        }
        self.obj = ExoToggle(system, data)

    async def test_toggle_not_implemented(self):
        with pytest.raises(NotImplementedError):
            await self.obj.toggle()


class TestExoAuxToggle(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.system = system = MagicMock()
        system.set_aux = async_noop
        data = {
            "name": "aux_1",
            "type": "Foo",
            "mode": "mode",
            "light": 0,
            "state": 0,
        }
        self.obj = ExoDevice.from_data(system, data)

    def test_from_data(self) -> None:
        assert isinstance(self.obj, ExoAuxToggle)

    def test_attributes(self) -> None:
        assert self.obj.name == "aux_1"
        assert self.obj.label == "Aux 1"
        assert self.obj.manufacturer == "Zodiac"
        assert self.obj.model == "AuxToggle"
        assert self.obj.state == "0"

    async def test_turn_on(self) -> None:
        self.system.set_aux.reset_mock()
        self.obj.data["state"] = 0
        await self.obj.turn_on()
        self.system.set_aux.assert_called_with("aux_1", 1)

    async def test_turn_on_noop(self) -> None:
        self.system.set_aux.reset_mock()
        self.obj.data["state"] = 1
        await self.obj.turn_on()
        self.system.set_aux.assert_not_called()

    async def test_turn_off(self) -> None:
        self.system.set_aux.reset_mock()
        self.obj.data["state"] = 1
        await self.obj.turn_off()
        self.system.set_aux.assert_called_with("aux_1", 0)

    async def test_turn_off_noop(self) -> None:
        self.system.set_aux.reset_mock()
        self.obj.data["state"] = 0
        await self.obj.turn_off()
        self.system.set_aux.assert_not_called()


class TestExoAttributeToggle(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.system = system = MagicMock()
        system.set_toggle = async_noop
        data = {
            "name": "boost",
            "state": 0,
        }
        self.obj = ExoDevice.from_data(system, data)

    def test_from_data(self) -> None:
        assert isinstance(self.obj, ExoAttributeToggle)

    def test_attributes(self):
        assert self.obj.name == "boost"
        assert self.obj.label == "Boost"
        assert self.obj.manufacturer == "Zodiac"
        assert self.obj.model == "AttributeToggle"
        assert self.obj.state == "0"

    async def test_turn_on(self) -> None:
        self.system.set_toggle.reset_mock()
        self.obj.data["state"] = 0
        await self.obj.turn_on()
        self.system.set_toggle.assert_called_with("boost", 1)

    async def test_turn_on_noop(self) -> None:
        self.system.set_toggle.reset_mock()
        self.obj.data["state"] = 1
        await self.obj.turn_on()
        self.system.set_toggle.assert_not_called()

    async def test_turn_off(self) -> None:
        self.system.set_toggle.reset_mock()
        self.obj.data["state"] = 1
        await self.obj.turn_off()
        self.system.set_toggle.assert_called_with("boost", 0)

    async def test_turn_off_noop(self) -> None:
        self.system.set_toggle.reset_mock()
        self.obj.data["state"] = 0
        await self.obj.turn_off()
        self.system.set_toggle.assert_not_called()


class TestExoThermostat(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.system = system = AsyncMock()
        system.set_toggle = async_noop
        data = {"name": "heating", "sp": 20, "sp_min": 1, "sp_max": 40}
        self.obj = ExoDevice.from_data(system, data)

    def test_from_data(self) -> None:
        assert isinstance(self.obj, ExoThermostat)

    def test_attributes(self):
        assert self.obj.name == "heating"
        assert self.obj.label == "Heating"
        assert self.obj.manufacturer == "Zodiac"
        assert self.obj.model == "Thermostat"
        assert self.obj.state == "20"
        assert self.obj.min_temperature == 1
        assert self.obj.max_temperature == 40

    async def test_bad_temperature(self):
        with pytest.raises(Exception):
            await self.obj.set_temperature(42)

    async def test_set_temperature(self):
        self.obj.system.set_temps.reset_mock()
        await self.obj.set_temperature(20)
        self.obj.system.set_temps.assert_called_once()
