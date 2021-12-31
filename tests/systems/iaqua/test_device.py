from __future__ import annotations

import copy
import unittest
from unittest.mock import MagicMock

import pytest

from iaqualink.systems.iaqua.device import (
    IaquaColorLight,
    IaquaDevice,
    IaquaDimmableLight,
    IaquaLightToggle,
    IaquaThermostat,
)

from ...common import async_noop


class TestIaquaDevice(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        system = MagicMock()
        data = {"name": "Test Device"}
        self.obj = IaquaDevice(system, data)

    def test_equal(self) -> None:
        assert self.obj == self.obj

    def test_not_equal(self) -> None:
        obj2 = copy.deepcopy(self.obj)
        obj2.data["name"] = "Test Device 2"
        assert self.obj != obj2

    def test_not_equal_different_type(self) -> None:
        assert (self.obj == {}) is False


class TestIaquaSensor(unittest.IsolatedAsyncioTestCase):
    pass


class TestIaquaToggle(unittest.IsolatedAsyncioTestCase):
    pass


class TestIaquaPump(unittest.IsolatedAsyncioTestCase):
    pass


class TestIaquaHeater(unittest.IsolatedAsyncioTestCase):
    pass


class TestIaquaAuxToggle(unittest.IsolatedAsyncioTestCase):
    pass


class TestIaquaLightToggle(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        system = MagicMock()
        system.set_aux = async_noop
        data = {"name": "Test Pool Light", "state": "0", "aux": "1"}
        self.obj = IaquaLightToggle(system, data)

    async def test_turn_off_noop(self) -> None:
        self.obj.system.set_aux.reset_mock()
        self.obj.data["state"] = "0"
        await self.obj.turn_off()
        self.obj.system.set_aux.assert_not_called()

    async def test_turn_off(self) -> None:
        self.obj.system.set_aux.reset_mock()
        self.obj.data["state"] = "1"
        await self.obj.turn_off()
        self.obj.system.set_aux.assert_called_once()

    async def test_turn_on(self) -> None:
        self.obj.system.set_aux.reset_mock()
        self.obj.data["state"] = "0"
        await self.obj.turn_on()
        self.obj.system.set_aux.assert_called_once()

    async def test_turn_on_noop(self) -> None:
        self.obj.system.set_aux.reset_mock()
        self.obj.data["state"] = "1"
        await self.obj.turn_on()
        self.obj.system.set_aux.assert_not_called()

    async def test_no_brightness(self) -> None:
        assert self.obj.brightness is None

    async def test_no_effect(self) -> None:
        assert self.obj.effect is None


class TestIaquaDimmableLight(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        system = MagicMock()
        system.set_light = async_noop
        data = {"name": "aux_1", "state": "0", "aux": "1", "subtype": "0"}
        self.obj = IaquaDimmableLight(system, data)

    def test_supports_brightness(self) -> None:
        assert self.obj.supports_brightness is True

    def test_supports_effect(self) -> None:
        assert self.obj.supports_effect is False

    def test_is_on_false(self) -> None:
        assert self.obj.is_on is False

    def test_is_on_true(self) -> None:
        self.obj.data["state"] = "1"
        self.obj.data["subtype"] = "50"
        assert self.obj.is_on is True

    async def test_turn_on(self) -> None:
        self.obj.system.set_light.reset_mock()
        await self.obj.turn_on()
        data = {"aux": "1", "light": "100"}
        self.obj.system.set_light.assert_called_once_with(data)

    async def test_turn_on_noop(self) -> None:
        self.obj.system.set_light.reset_mock()
        self.obj.data["state"] = "1"
        self.obj.data["subtype"] = "100"
        await self.obj.turn_on()
        self.obj.system.set_light.assert_not_called()

    async def test_turn_off(self) -> None:
        self.obj.system.set_light.reset_mock()
        self.obj.data["state"] = "1"
        self.obj.data["subtype"] = "100"
        await self.obj.turn_off()
        data = {"aux": "1", "light": "0"}
        self.obj.system.set_light.assert_called_once_with(data)

    async def test_turn_off_noop(self) -> None:
        self.obj.system.set_light.reset_mock()
        await self.obj.turn_off()
        self.obj.system.set_light.assert_not_called()

    async def test_bad_brightness(self) -> None:
        self.obj.system.set_light.reset_mock()
        with pytest.raises(Exception):
            await self.obj.set_brightness(89)

    async def test_set_brightness(self) -> None:
        self.obj.system.set_light.reset_mock()
        await self.obj.set_brightness(75)
        data = {"aux": "1", "light": "75"}
        self.obj.system.set_light.assert_called_once_with(data)


class TestIaquaColorLight(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        system = MagicMock()
        system.set_light = async_noop
        data = {
            "name": "aux_1",
            "aux": "1",
            "state": "0",
            "type": "2",
            "subtype": "5",
        }
        self.obj = IaquaColorLight(system, data)

    def test_supports_brightness(self) -> None:
        assert self.obj.supports_brightness is False

    def test_supports_effect(self) -> None:
        assert self.obj.supports_effect is True

    def test_is_on_false(self) -> None:
        assert self.obj.is_on is False

    def test_is_on_true(self) -> None:
        self.obj.data["state"] = "2"
        assert self.obj.is_on is True

    async def test_turn_off_noop(self) -> None:
        self.obj.system.set_light.reset_mock()
        await self.obj.turn_off()
        self.obj.system.set_light.assert_not_called()

    async def test_turn_off(self) -> None:
        self.obj.system.set_light.reset_mock()
        self.obj.data["state"] = "1"
        await self.obj.turn_off()
        data = {"aux": "1", "light": "0", "subtype": "5"}
        self.obj.system.set_light.assert_called_once_with(data)

    async def test_turn_on(self) -> None:
        self.obj.system.set_light.reset_mock()
        await self.obj.turn_on()
        data = {"aux": "1", "light": "1", "subtype": "5"}
        self.obj.system.set_light.assert_called_once_with(data)

    async def test_turn_on_noop(self) -> None:
        self.obj.system.set_light.reset_mock()
        self.obj.data["state"] = "1"
        await self.obj.turn_on()
        self.obj.system.set_light.assert_not_called()

    async def test_set_effect(self) -> None:
        self.obj.system.set_light.reset_mock()
        data = {"aux": "1", "light": "2", "subtype": "5"}
        await self.obj.set_effect_by_id(2)
        self.obj.system.set_light.assert_called_once_with(data)

    async def test_set_effect_invalid(self) -> None:
        self.obj.system.set_light.reset_mock()
        with pytest.raises(Exception):
            await self.obj.set_effect_by_name("bad effect name")


class TestIaquaThermostat(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.system = system = MagicMock()
        self.system.temp_unit = "F"
        system.set_temps = async_noop
        pool_data = {"name": "pool_set_point", "state": "76"}
        self.pool_obj = IaquaThermostat(system, pool_data)
        spa_data = {"name": "spa_set_point", "state": "102"}
        self.spa_obj = IaquaThermostat(system, spa_data)

    async def test_temp_name_spa_present(self):
        self.system.has_spa = True
        assert self.spa_obj._temperature == "temp1"
        assert self.pool_obj._temperature == "temp2"

    async def test_temp_name_no_spa(self):
        self.system.has_spa = False
        assert self.pool_obj._temperature == "temp1"

    async def test_bad_temperature(self):
        with pytest.raises(Exception):
            await self.pool_obj.set_temperature(18)

    async def test_bad_temperature_2(self):
        self.system.temp_unit = "C"
        with pytest.raises(Exception):
            await self.pool_obj.set_temperature(72)

    async def test_set_temperature(self):
        self.pool_obj.system.set_temps.reset_mock()
        await self.pool_obj.set_temperature(72)
        self.pool_obj.system.set_temps.assert_called_once()

    async def test_set_temperature_2(self):
        self.pool_obj.system.set_temps.reset_mock()
        self.system.temp_unit = "C"
        await self.pool_obj.set_temperature(18)
        self.pool_obj.system.set_temps.assert_called_once()
