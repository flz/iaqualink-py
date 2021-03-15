from __future__ import annotations

import unittest
from unittest.mock import MagicMock
import pytest

from iaqualink.device import (
    AqualinkColorLight,
    AqualinkDimmableLight,
    AqualinkLightToggle,
    AqualinkThermostat,
)

from .common import async_noop


class TestAqualinkDevice(unittest.IsolatedAsyncioTestCase):
    pass


class TestAqualinkSensor(unittest.IsolatedAsyncioTestCase):
    pass


class TestAqualinkToggle(unittest.IsolatedAsyncioTestCase):
    pass


class TestAqualinkPump(unittest.IsolatedAsyncioTestCase):
    pass


class TestAqualinkHeater(unittest.IsolatedAsyncioTestCase):
    pass


class TestAqualinkAuxToggle(unittest.IsolatedAsyncioTestCase):
    pass


class TestAqualinkLightToggle(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        system = MagicMock()
        system.set_aux = async_noop
        data = {"name": "Test Pool Light", "state": "0", "aux": "1"}
        self.obj = AqualinkLightToggle(system, data)

    async def test_turn_off_noop(self) -> None:
        self.obj.system.set_aux.reset_mock()
        await self.obj.turn_off()
        self.obj.system.set_aux.assert_not_called()

    async def test_turn_off(self) -> None:
        self.obj.system.set_aux.reset_mock()
        self.obj.data["state"] = "1"
        await self.obj.turn_off()
        self.obj.system.set_aux.assert_called_once()

    async def test_turn_on(self) -> None:
        self.obj.system.set_aux.reset_mock()
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


class TestAqualinkDimmableLight(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        system = MagicMock()
        system.set_light = async_noop
        data = {"name": "aux_1", "state": "0", "aux": "1", "subtype": "0"}
        self.obj = AqualinkDimmableLight(system, data)

    def test_is_dimmer(self) -> None:
        assert self.obj.is_dimmer is True

    def test_is_color(self) -> None:
        assert self.obj.is_color is False

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


class TestAqualinkColorLight(unittest.IsolatedAsyncioTestCase):
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
        self.obj = AqualinkColorLight(system, data)

    def test_is_dimmer(self) -> None:
        assert self.obj.is_dimmer is False

    def test_is_color(self) -> None:
        assert self.obj.is_color is True

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
        await self.obj.set_effect_by_num("2")
        self.obj.system.set_light.assert_called_once_with(data)

    async def test_set_effect_invalid(self) -> None:
        self.obj.system.set_light.reset_mock()
        with pytest.raises(Exception):
            await self.obj.set_effect_by_name("bad effect name")


class TestAqualinkThermostat(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.system = system = MagicMock()
        self.system.temp_unit = "F"
        system.set_temps = async_noop
        pool_data = {"name": "pool_set_point", "state": "76"}
        self.pool_obj = AqualinkThermostat(system, pool_data)
        spa_data = {"name": "spa_set_point", "state": "102"}
        self.spa_obj = AqualinkThermostat(system, spa_data)

    async def test_temp_name_spa_present(self):
        self.system.has_spa = True
        assert self.spa_obj.temp == "temp1"
        assert self.pool_obj.temp == "temp2"

    async def test_temp_name_no_spa(self):
        self.system.has_spa = False
        assert self.pool_obj.temp == "temp1"

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
