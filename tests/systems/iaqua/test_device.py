from __future__ import annotations

import copy
from typing import cast
from unittest.mock import patch

from iaqualink.systems.iaqua.device import (
    IAQUA_TEMP_CELSIUS_HIGH,
    IAQUA_TEMP_CELSIUS_LOW,
    IAQUA_TEMP_FAHRENHEIT_HIGH,
    IAQUA_TEMP_FAHRENHEIT_LOW,
    IaquaAuxSwitch,
    IaquaBinarySensor,
    IaquaColorLight,
    IaquaDevice,
    IaquaDimmableLight,
    IaquaLightSwitch,
    IaquaSensor,
    IaquaSwitch,
    IaquaThermostat,
)
from iaqualink.systems.iaqua.system import IaquaSystem

from ...base_test_device import (
    TestBaseBinarySensor,
    TestBaseDevice,
    TestBaseLight,
    TestBaseSensor,
    TestBaseSwitch,
    TestBaseThermostat,
)


class TestIaquaDevice(TestBaseDevice):
    def setUp(self) -> None:
        super().setUp()

        data = {"serial_number": "SN123456", "device_type": "iaqua"}
        self.system = IaquaSystem(self.client, data=data)

        data = {"name": "device", "state": "42"}
        self.sut = IaquaDevice(self.system, data)
        self.sut_class = IaquaDevice

    def test_equal(self) -> None:
        assert self.sut == self.sut

    def test_not_equal(self) -> None:
        obj2 = copy.deepcopy(self.sut)
        obj2.data["name"] = "device_2"
        assert self.sut != obj2

    def test_property_name(self) -> None:
        assert self.sut.name == self.sut.data["name"]

    def test_property_state(self) -> None:
        assert self.sut.state == self.sut.data["state"]

    def test_not_equal_different_type(self) -> None:
        assert (self.sut == {}) is False

    def test_property_manufacturer(self) -> None:
        assert self.sut.manufacturer == "Jandy"

    def test_property_model(self) -> None:
        assert self.sut.model == self.sut_class.__name__.replace("Iaqua", "")


class TestIaquaSensor(TestIaquaDevice, TestBaseSensor):
    def setUp(self) -> None:
        super().setUp()

        data = {"name": "orp", "state": "42"}
        self.sut = IaquaDevice.from_data(self.system, data)
        self.sut_class = IaquaSensor


class TestIaquaBinarySensor(TestIaquaSensor, TestBaseBinarySensor):
    def setUp(self) -> None:
        super().setUp()

        data = {"name": "freeze_protection", "state": "0"}
        self.sut_class = IaquaBinarySensor
        self.sut = IaquaDevice.from_data(self.system, data)

    def test_property_is_on_false(self) -> None:
        self.sut.data["state"] = "0"
        super().test_property_is_on_false()
        assert self.sut.is_on is False

    def test_property_is_on_true(self) -> None:
        self.sut.data["state"] = "1"
        super().test_property_is_on_true()
        assert self.sut.is_on is True


class TestIaquaSwitch(TestIaquaBinarySensor, TestBaseSwitch):
    def setUp(self) -> None:
        super().setUp()

        data = {
            "name": "pool_heater",
            "state": "0",
        }
        self.sut = IaquaDevice.from_data(self.system, data)
        self.sut_class = IaquaSwitch

    async def test_turn_on(self) -> None:
        self.sut.data["state"] = "0"
        with patch.object(self.sut.system, "_parse_home_response"):
            await super().test_turn_on()

    async def test_turn_on_noop(self) -> None:
        self.sut.data["state"] = "1"
        with patch.object(self.sut.system, "_parse_home_response"):
            await super().test_turn_on_noop()

    async def test_turn_off(self) -> None:
        self.sut.data["state"] = "1"
        with patch.object(self.sut.system, "_parse_home_response"):
            await super().test_turn_off()

    async def test_turn_off_noop(self) -> None:
        self.sut.data["state"] = "0"
        with patch.object(self.sut.system, "_parse_home_response"):
            await super().test_turn_off_noop()


class TestIaquaAuxSwitch(TestIaquaSwitch, TestBaseSwitch):
    def setUp(self) -> None:
        super().setUp()

        data = {
            "name": "aux_1",
            "state": "0",
            "aux": "1",
            "type": "0",
            "label": "CLEANER",
        }
        self.sut = IaquaDevice.from_data(self.system, data)
        self.sut_class = IaquaAuxSwitch

    async def test_turn_on(self) -> None:
        self.sut.data["state"] = "0"
        with patch.object(self.sut.system, "_parse_devices_response"):
            await super().test_turn_on()

    async def test_turn_on_noop(self) -> None:
        self.sut.data["state"] = "1"
        with patch.object(self.sut.system, "_parse_devices_response"):
            await super().test_turn_on_noop()

    async def test_turn_off(self) -> None:
        self.sut.data["state"] = "1"
        with patch.object(self.sut.system, "_parse_devices_response"):
            await super().test_turn_off()

    async def test_turn_off_noop(self) -> None:
        self.sut.data["state"] = "0"
        with patch.object(self.sut.system, "_parse_devices_response"):
            await super().test_turn_off_noop()


class TestIaquaLightSwitch(TestIaquaAuxSwitch, TestBaseLight):
    def setUp(self) -> None:
        super().setUp()

        # system.set_aux = async_noop
        data = {
            "name": "aux_1",
            "state": "0",
            "aux": "1",
            "label": "POOL LIGHT",
            "type": "0",
        }
        self.sut = IaquaDevice.from_data(self.system, data)
        self.sut_class = IaquaLightSwitch

    def test_property_brightness(self) -> None:
        assert self.sut.brightness is None

    def test_property_effect(self) -> None:
        assert self.sut.effect is None


class TestIaquaDimmableLight(TestIaquaAuxSwitch, TestBaseLight):
    def setUp(self) -> None:
        super().setUp()

        data = {
            "name": "aux_1",
            "state": "1",
            "aux": "1",
            "subtype": "25",
            "type": "1",
            "label": "SPA LIGHT",
        }
        self.sut = IaquaDevice.from_data(self.system, data)
        self.sut_class = IaquaDimmableLight

    def test_property_name(self) -> None:
        super().test_property_name()
        assert self.sut.name == "aux_1"

    def test_property_label(self) -> None:
        super().test_property_label()
        assert self.sut.label == "Spa Light"

    def test_property_state(self) -> None:
        super().test_property_state()
        assert self.sut.state == "1"

    def test_property_is_on_false(self) -> None:
        self.sut.data["state"] = "0"
        self.sut.data["subtype"] = "0"
        super().test_property_is_on_false()
        assert self.sut.is_on is False

    def test_property_is_on_true(self) -> None:
        self.sut.data["state"] = "1"
        self.sut.data["subtype"] = "100"
        super().test_property_is_on_true()
        assert self.sut.is_on is True

    async def test_turn_on(self) -> None:
        self.sut.data["state"] = "0"
        self.sut.data["subtype"] = "0"
        with patch.object(self.sut.system, "_parse_devices_response"):
            await super().test_turn_on()

    async def test_turn_on_noop(self) -> None:
        self.sut.data["state"] = "1"
        self.sut.data["subtype"] = "25"
        with patch.object(self.sut.system, "_parse_devices_response"):
            await super().test_turn_on_noop()

    async def test_turn_off(self) -> None:
        self.sut.data["state"] = "1"
        self.sut.data["subtype"] = "100"
        with patch.object(self.sut.system, "_parse_devices_response"):
            await super().test_turn_off()

    async def test_turn_off_noop(self) -> None:
        self.sut.data["state"] = "0"
        self.sut.data["subtype"] = "0"
        with patch.object(self.sut.system, "_parse_devices_response"):
            await super().test_turn_off_noop()

    def test_property_supports_brightness(self) -> None:
        super().test_property_supports_brightness()
        assert self.sut.supports_brightness is True

    def test_property_supports_effect(self) -> None:
        super().test_property_supports_effect()
        assert self.sut.supports_effect is False

    async def test_set_brightness_75(self) -> None:
        with patch.object(self.sut.system, "_parse_devices_response"):
            await super().test_set_brightness_75()


class TestIaquaColorLight(TestIaquaAuxSwitch, TestBaseLight):
    def setUp(self) -> None:
        super().setUp()

        # system.set_light = async_noop
        data = {
            "name": "aux_1",
            "aux": "1",
            "state": "0",
            "type": "2",
            "subtype": "5",
            "label": "POOL LIGHT",
        }
        self.sut = IaquaDevice.from_data(self.system, data)
        self.sut_class = IaquaColorLight

    def test_property_name(self) -> None:
        super().test_property_name()
        assert self.sut.name == "aux_1"

    def test_property_label(self) -> None:
        super().test_property_label()
        assert self.sut.label == "Pool Light"

    def test_property_state(self) -> None:
        super().test_property_state()

    def test_property_manufacturer(self) -> None:
        assert self.sut.manufacturer == "Pentair"

    def test_property_model(self) -> None:
        assert self.sut.model == "Intellibrite Light"

    def test_property_supports_brightness(self) -> None:
        super().test_property_supports_brightness()
        assert self.sut.supports_brightness is False

    def test_property_supports_effect(self) -> None:
        super().test_property_supports_effect()
        assert self.sut.supports_effect is True

    async def test_turn_off(self) -> None:
        self.sut.data["state"] = "1"
        with patch.object(self.sut.system, "_parse_devices_response"):
            await super().test_turn_off()
        # data = {"aux": "1", "light": "0", "subtype": "5"}

    async def test_turn_on(self) -> None:
        self.sut.data["state"] = "0"
        with patch.object(self.sut.system, "_parse_devices_response"):
            await super().test_turn_on()
        # data = {"aux": "1", "light": "1", "subtype": "5"}

    async def test_set_effect_by_id_4(self) -> None:
        with patch.object(self.sut.system, "_parse_devices_response"):
            await super().test_set_effect_by_id_4()
        # data = {"aux": "1", "light": "2", "subtype": "5"}

    async def test_set_effect_by_id_invalid_27(self) -> None:
        with patch.object(self.sut.system, "_parse_devices_response"):
            await super().test_set_effect_by_id_invalid_27()

    async def test_set_effect_by_name_off(self) -> None:
        with patch.object(self.sut.system, "_parse_devices_response"):
            await super().test_set_effect_by_name_off()

    async def test_set_effect_by_name_invalid_amaranth(self) -> None:
        with patch.object(self.sut.system, "_parse_devices_response"):
            await super().test_set_effect_by_name_invalid_amaranth()


class TestIaquaThermostat(TestIaquaDevice, TestBaseThermostat):
    def setUp(self) -> None:
        super().setUp()

        pool_set_point = {"name": "pool_set_point", "state": "86"}
        self.pool_set_point = cast(
            IaquaThermostat, IaquaDevice.from_data(self.system, pool_set_point)
        )

        pool_temp = {"name": "pool_temp", "state": "65"}
        self.pool_temp = IaquaDevice.from_data(self.system, pool_temp)

        pool_heater = {"name": "pool_heater", "state": "0"}
        self.pool_heater = IaquaDevice.from_data(self.system, pool_heater)

        spa_set_point = {"name": "spa_set_point", "state": "102"}
        self.spa_set_point = cast(
            IaquaThermostat, IaquaDevice.from_data(self.system, spa_set_point)
        )

        devices = [
            self.pool_set_point,
            self.pool_heater,
            self.pool_temp,
        ]
        self.system.devices = {x.name: x for x in devices}

        self.sut = self.pool_set_point
        self.sut_class = IaquaThermostat

    def test_property_label(self) -> None:
        assert self.sut.label == "Pool Set Point"

    def test_property_name(self) -> None:
        assert self.sut.name == "pool_set_point"

    def test_property_state(self) -> None:
        assert self.sut.state == "86"

    def test_property_is_on_true(self) -> None:
        self.pool_heater.data["state"] = "1"
        super().test_property_is_on_true()

    def test_property_is_on_false(self) -> None:
        self.pool_heater.data["state"] = "0"
        super().test_property_is_on_false()

    def test_property_unit(self) -> None:
        self.sut.system.temp_unit = "F"
        super().test_property_unit()

    def test_property_min_temperature_f(self) -> None:
        self.sut.system.temp_unit = "F"
        super().test_property_min_temperature_c()
        assert self.sut.min_temperature == IAQUA_TEMP_FAHRENHEIT_LOW

    def test_property_min_temperature_c(self) -> None:
        self.sut.system.temp_unit = "C"
        super().test_property_min_temperature_f()
        assert self.sut.min_temperature == IAQUA_TEMP_CELSIUS_LOW

    def test_property_max_temperature_f(self) -> None:
        self.sut.system.temp_unit = "F"
        super().test_property_max_temperature_f()
        assert self.sut.max_temperature == IAQUA_TEMP_FAHRENHEIT_HIGH

    def test_property_max_temperature_c(self) -> None:
        self.sut.system.temp_unit = "C"
        super().test_property_max_temperature_c()
        assert self.sut.max_temperature == IAQUA_TEMP_CELSIUS_HIGH

    def test_property_current_temperature(self) -> None:
        super().test_property_current_temperature()
        assert self.sut.current_temperature == "65"

    def test_property_target_temperature(self) -> None:
        super().test_property_target_temperature()
        assert self.sut.target_temperature == "86"

    async def test_turn_on(self) -> None:
        self.pool_heater.data["state"] = "0"
        with patch.object(self.sut.system, "_parse_home_response"):
            await super().test_turn_on()
        assert len(self.respx_calls) == 1
        url = str(self.respx_calls[0].request.url)
        assert "set_pool_heater" in url

    async def test_turn_on_noop(self) -> None:
        self.pool_heater.data["state"] = "1"
        await super().test_turn_on_noop()

    async def test_turn_off(self) -> None:
        self.pool_heater.data["state"] = "1"
        with patch.object(self.sut.system, "_parse_home_response"):
            await super().test_turn_off()
        assert len(self.respx_calls) == 1
        url = str(self.respx_calls[0].request.url)
        assert "set_pool_heater" in url

    async def test_turn_off_noop(self) -> None:
        self.pool_heater.data["state"] = "0"
        await super().test_turn_off_noop()

    async def test_set_temperature_86f(self) -> None:
        with patch.object(self.sut.system, "_parse_home_response"):
            await super().test_set_temperature_86f()
        assert len(self.respx_calls) == 1
        url = str(self.respx_calls[0].request.url)
        assert "86" in url

    async def test_set_temperature_30c(self) -> None:
        with patch.object(self.sut.system, "_parse_home_response"):
            await super().test_set_temperature_30c()
        assert len(self.respx_calls) == 1
        url = str(self.respx_calls[0].request.url)
        assert "30" in url

    async def test_temp_name_spa_present(self) -> None:
        self.sut.system.devices["spa_set_point"] = self.spa_set_point
        assert self.spa_set_point._temperature == "temp1"
        assert self.pool_set_point._temperature == "temp2"

    async def test_temp_name_no_spa(self) -> None:
        assert self.pool_set_point._temperature == "temp1"
