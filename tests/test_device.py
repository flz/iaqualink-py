import asynctest
import pytest

from iaqualink.device import (
    AqualinkDimmableLight,
    AqualinkLightToggle,
    AqualinkThermostat,
)


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
        data = {"name": "aux_1", "state": "0", "aux": "1", "label": "LIGHT"}
        self.obj = AqualinkDimmableLight(system, data)

    @asynctest.strict
    async def test_bad_brightness(self) -> None:
        with pytest.raises(Exception):
            await self.obj.set_brightness(89)


# XXX - No tests right now since I'm not 100% sure how it works.
class TestAqualinkColorLight(asynctest.TestCase):
    pass


class TestAqualinkThermostat(asynctest.TestCase):
    def setUp(self) -> None:
        self.system = system = asynctest.MagicMock()
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
            await self.pool_obj.set_temperature(1000)

    @asynctest.strict
    async def test_set_temperature(self):
        await self.pool_obj.set_temperature(80)
        self.pool_obj.system.set_temps.assert_called_once()
