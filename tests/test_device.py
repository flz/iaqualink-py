from __future__ import annotations

import asynctest
import pytest

from iaqualink.device import (
    AqualinkColorLight,
    AqualinkDimmableLight,
    AqualinkLightToggle,
    AqualinkThermostat,
)


pytestmark = pytest.mark.asyncio


class TestAqualinkDevice(asynctest.TestCase):
    pass


class TestAqualinkSensor(asynctest.TestCase):
    pass


class TestAqualinkToggle(asynctest.TestCase):
    pass


class TestAqualinkPump(asynctest.TestCase):
    pass


class TestAqualinkHeater(asynctest.TestCase):
    pass


class TestAqualinkAuxToggle(asynctest.TestCase):
    pass


class TestAqualinkLightToggle(asynctest.TestCase):
    def setUp(self) -> None:
        system = asynctest.MagicMock()
        system.set_aux = asynctest.CoroutineMock(return_value=None)
        data = {"name": "Test Pool Light", "state": "0", "aux": "1"}
        self.obj = AqualinkLightToggle(system, data)

    @asynctest.strict
    async def test_turn_off_noop(self) -> None:
        await self.obj.turn_off()
        self.obj.system.set_aux.assert_not_called()

    @asynctest.strict
    async def test_turn_off(self) -> None:
        self.obj.data["state"] = "1"
        await self.obj.turn_off()
        self.obj.system.set_aux.assert_called_once()

    @asynctest.strict
    async def test_turn_on(self) -> None:
        await self.obj.turn_on()
        self.obj.system.set_aux.assert_called_once()

    @asynctest.strict
    async def test_turn_on_noop(self) -> None:
        self.obj.data["state"] = "1"
        await self.obj.turn_on()
        self.obj.system.set_aux.assert_not_called()

    @asynctest.strict
    async def test_no_brightness(self) -> None:
        assert self.obj.brightness is None

    @asynctest.strict
    async def test_no_effect(self) -> None:
        assert self.obj.effect is None


class TestAqualinkDimmableLight(asynctest.TestCase):
    def setUp(self) -> None:
        system = asynctest.MagicMock()
        system.set_light = asynctest.CoroutineMock(return_value=None)
        data = {"name": "aux_1", "state": "0", "aux": "1", "subtype": "0"}
        self.obj = AqualinkDimmableLight(system, data)

    @asynctest.fail_on(unused_loop=False)
    def test_is_dimmer(self) -> None:
        assert self.obj.is_dimmer is True

    @asynctest.fail_on(unused_loop=False)
    def test_is_color(self) -> None:
        assert self.obj.is_color is False

    @asynctest.fail_on(unused_loop=False)
    def test_is_on_false(self) -> None:
        assert self.obj.is_on is False

    @asynctest.fail_on(unused_loop=False)
    def test_is_on_true(self) -> None:
        self.obj.data["state"] = "1"
        self.obj.data["subtype"] = "50"
        assert self.obj.is_on is True

    @asynctest.strict
    async def test_turn_on(self) -> None:
        await self.obj.turn_on()
        data = {"aux": "1", "light": "100"}
        self.obj.system.set_light.assert_called_once_with(data)

    @asynctest.strict
    async def test_turn_on_noop(self) -> None:
        self.obj.data["state"] = "1"
        self.obj.data["subtype"] = "100"
        await self.obj.turn_on()
        self.obj.system.set_light.assert_not_called()

    @asynctest.strict
    async def test_turn_off(self) -> None:
        self.obj.data["state"] = "1"
        self.obj.data["subtype"] = "100"
        await self.obj.turn_off()
        data = {"aux": "1", "light": "0"}
        self.obj.system.set_light.assert_called_once_with(data)

    @asynctest.strict
    async def test_turn_off_noop(self) -> None:
        await self.obj.turn_off()
        self.obj.system.set_light.assert_not_called()

    @asynctest.strict
    async def test_bad_brightness(self) -> None:
        with pytest.raises(Exception):
            await self.obj.set_brightness(89)

    @asynctest.strict
    async def test_set_brightness(self) -> None:
        await self.obj.set_brightness(75)
        data = {"aux": "1", "light": "75"}
        self.obj.system.set_light.assert_called_once_with(data)


class TestAqualinkColorLight(asynctest.TestCase):
    def setUp(self) -> None:
        system = asynctest.MagicMock()
        system.set_light = asynctest.CoroutineMock(return_value=None)
        data = {
            "name": "aux_1",
            "aux": "1",
            "state": "0",
            "type": "2",
            "subtype": "5",
        }
        self.obj = AqualinkColorLight(system, data)

    @asynctest.fail_on(unused_loop=False)
    def test_is_dimmer(self) -> None:
        assert self.obj.is_dimmer is False

    @asynctest.fail_on(unused_loop=False)
    def test_is_color(self) -> None:
        assert self.obj.is_color is True

    @asynctest.fail_on(unused_loop=False)
    def test_is_on_false(self) -> None:
        assert self.obj.is_on is False

    @asynctest.fail_on(unused_loop=False)
    def test_is_on_true(self) -> None:
        self.obj.data["state"] = "2"
        assert self.obj.is_on is True

    @asynctest.strict
    async def test_turn_off_noop(self) -> None:
        await self.obj.turn_off()
        self.obj.system.set_light.assert_not_called()

    @asynctest.strict
    async def test_turn_off(self) -> None:
        self.obj.data["state"] = "1"
        await self.obj.turn_off()
        data = {"aux": "1", "light": "0", "subtype": "5"}
        self.obj.system.set_light.assert_called_once_with(data)

    @asynctest.strict
    async def test_turn_on(self) -> None:
        await self.obj.turn_on()
        data = {"aux": "1", "light": "1", "subtype": "5"}
        self.obj.system.set_light.assert_called_once_with(data)

    @asynctest.strict
    async def test_turn_on_noop(self) -> None:
        self.obj.data["state"] = "1"
        await self.obj.turn_on()
        self.obj.system.set_light.assert_not_called()

    @asynctest.strict
    async def test_set_effect(self) -> None:
        data = {"aux": "1", "light": "2", "subtype": "5"}
        await self.obj.set_effect_by_num("2")
        self.obj.system.set_light.assert_called_once_with(data)

    @asynctest.strict
    async def test_set_effect_invalid(self) -> None:
        self.obj.system.set_light = asynctest.CoroutineMock(return_value=None)
        with pytest.raises(Exception):
            await self.obj.set_effect_by_name("bad effect name")


class TestAqualinkThermostat(asynctest.TestCase):
    def setUp(self) -> None:
        self.system = system = asynctest.MagicMock()
        self.system.temp_unit = "F"
        system.set_temps = asynctest.CoroutineMock(return_value=None)
        pool_data = {"name": "pool_set_point", "state": "76"}
        self.pool_obj = AqualinkThermostat(system, pool_data)
        spa_data = {"name": "spa_set_point", "state": "102"}
        self.spa_obj = AqualinkThermostat(system, spa_data)

    @asynctest.strict
    async def test_temp_name_spa_present(self):
        self.system.has_spa = True
        assert self.spa_obj.temp == "temp1"
        assert self.pool_obj.temp == "temp2"

    @asynctest.strict
    async def test_temp_name_no_spa(self):
        self.system.has_spa = False
        assert self.pool_obj.temp == "temp1"

    @asynctest.strict
    async def test_bad_temperature(self):
        with pytest.raises(Exception):
            await self.pool_obj.set_temperature(18)

    @asynctest.strict
    async def test_bad_temperature_2(self):
        self.system.temp_unit = "C"
        with pytest.raises(Exception):
            await self.pool_obj.set_temperature(72)

    @asynctest.strict
    async def test_set_temperature(self):
        await self.pool_obj.set_temperature(72)
        self.pool_obj.system.set_temps.assert_called_once()

    @asynctest.strict
    async def test_set_temperature_2(self):
        self.system.temp_unit = "C"
        await self.pool_obj.set_temperature(18)
        self.pool_obj.system.set_temps.assert_called_once()
