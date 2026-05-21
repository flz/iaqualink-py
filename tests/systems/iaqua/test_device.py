from __future__ import annotations

import copy
from unittest.mock import patch

import pytest
import respx
import respx.router

from iaqualink.exception import AqualinkStateUnavailableException
from iaqualink.systems.iaqua.device import (
    IAQUA_TEMP_CELSIUS_HIGH,
    IAQUA_TEMP_CELSIUS_LOW,
    IAQUA_TEMP_FAHRENHEIT_HIGH,
    IAQUA_TEMP_FAHRENHEIT_LOW,
    IaquaAuxSwitch,
    IaquaBinarySensor,
    IaquaClimate,
    IaquaColorLight,
    IaquaColorLightIB,
    IaquaDevice,
    IaquaDimmableLight,
    IaquaHeater,
    IaquaLightSwitch,
    IaquaOneTouchSwitch,
    IaquaPresenceSensor,
    IaquaSensor,
    IaquaSetPoint,
    IaquaSwitch,
)
from iaqualink.systems.iaqua.enums import IaquaTemperatureUnit
from iaqualink.systems.iaqua.system import IaquaSystem

from ...base import dotstar, resp_200
from ...base_test_device import (
    TestBaseBinarySensor,
    TestBaseClimate,
    TestBaseDevice,
    TestBaseLight,
    TestBaseNumber,
    TestBaseSensor,
    TestBaseSwitch,
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
        self.sut = IaquaSensor(self.system, data)
        self.sut_class = IaquaSensor

    def test_property_value(self) -> None:
        assert self.sut.value == self.sut.data["state"]


class TestIaquaBinarySensor(TestIaquaDevice, TestBaseBinarySensor):
    def setUp(self) -> None:
        super().setUp()

        data = {"name": "freeze_protection", "state": "0"}
        self.sut_class = IaquaBinarySensor
        self.sut = IaquaBinarySensor(self.system, data)

    def test_property_is_on_false(self) -> None:
        self.sut.data["state"] = "0"
        super().test_property_is_on_false()
        assert self.sut.is_on is False

    def test_property_is_on_true(self) -> None:
        self.sut.data["state"] = "1"
        super().test_property_is_on_true()
        assert self.sut.is_on is True


class TestIaquaPresenceSensor(TestIaquaBinarySensor):
    def setUp(self) -> None:
        super().setUp()

        data = {"name": "is_icl_present", "state": "present"}
        self.sut_class = IaquaPresenceSensor
        self.sut = IaquaPresenceSensor(self.system, data)

    def test_property_is_on_true(self) -> None:
        self.sut.data["state"] = "present"
        assert self.sut.is_on is True

    def test_property_is_on_false(self) -> None:
        self.sut.data["state"] = "absent"
        assert self.sut.is_on is False

    def test_property_is_on_false_empty(self) -> None:
        self.sut.data["state"] = ""
        assert self.sut.is_on is False


class TestIaquaSwitch(TestIaquaDevice, TestBaseSwitch):
    def setUp(self) -> None:
        super().setUp()

        data = {
            "name": "pool_pump",
            "state": "0",
        }
        self.sut = IaquaSwitch(self.system, data)
        self.sut_class = IaquaSwitch

    def test_property_is_on_false(self) -> None:
        self.sut.data["state"] = "0"
        super().test_property_is_on_false()

    def test_property_is_on_true(self) -> None:
        self.sut.data["state"] = "1"
        super().test_property_is_on_true()

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


class TestIaquaHeater(TestIaquaDevice, TestBaseSwitch):
    def setUp(self) -> None:
        super().setUp()

        data = {
            "name": "pool_heater",
            "state": "0",
        }
        self.sut = IaquaHeater(self.system, data)
        self.sut_class = IaquaHeater

    def test_property_is_on_false(self) -> None:
        self.sut.data["state"] = "0"
        super().test_property_is_on_false()

    def test_property_is_on_true(self) -> None:
        self.sut.data["state"] = "1"
        super().test_property_is_on_true()

    def test_property_is_on_enabled(self) -> None:
        self.sut.data["state"] = "3"
        assert self.sut.is_on is True

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


class TestIaquaOneTouchSwitch(TestIaquaSwitch, TestBaseSwitch):
    def setUp(self) -> None:
        super().setUp()

        data = {
            "name": "onetouch_1",
            "state": "0",
            "label": "Morning Scene",
            "status": "1",
        }
        self.sut = IaquaOneTouchSwitch(self.system, data)
        self.sut_class = IaquaOneTouchSwitch

    async def test_turn_on(self) -> None:
        self.sut.data["state"] = "0"
        with patch.object(self.sut.system, "_parse_onetouch_response"):
            await super().test_turn_on()

    async def test_turn_on_noop(self) -> None:
        self.sut.data["state"] = "1"
        with patch.object(self.sut.system, "_parse_onetouch_response"):
            await super().test_turn_on_noop()

    async def test_turn_off(self) -> None:
        self.sut.data["state"] = "1"
        with patch.object(self.sut.system, "_parse_onetouch_response"):
            await super().test_turn_off()

    async def test_turn_off_noop(self) -> None:
        self.sut.data["state"] = "0"
        with patch.object(self.sut.system, "_parse_onetouch_response"):
            await super().test_turn_off_noop()

    def test_property_label(self) -> None:
        super().test_property_label()
        assert self.sut.label == "Morning Scene"


class TestIaquaAuxSwitch(TestIaquaDevice, TestBaseSwitch):
    def setUp(self) -> None:
        super().setUp()

        data = {
            "name": "aux_1",
            "state": "0",
            "aux": "1",
            "type": "0",
            "label": "CLEANER",
        }
        self.sut = IaquaAuxSwitch(self.system, data)
        self.sut_class = IaquaAuxSwitch

    def test_property_is_on_false(self) -> None:
        self.sut.data["state"] = "0"
        super().test_property_is_on_false()

    def test_property_is_on_true(self) -> None:
        self.sut.data["state"] = "1"
        super().test_property_is_on_true()

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


class TestIaquaLightSwitch(TestIaquaDevice, TestBaseLight):
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
        self.sut = IaquaLightSwitch(self.system, data)
        self.sut_class = IaquaLightSwitch

    def test_property_is_on_false(self) -> None:
        self.sut.data["state"] = "0"
        super().test_property_is_on_false()

    def test_property_is_on_true(self) -> None:
        self.sut.data["state"] = "1"
        super().test_property_is_on_true()

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

    def test_property_brightness_percentage(self) -> None:
        assert self.sut.brightness_percentage is None

    def test_property_effect(self) -> None:
        assert self.sut.effect is None


class TestIaquaDimmableLight(TestIaquaDevice, TestBaseLight):
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
        self.sut = IaquaDimmableLight(self.system, data)
        self.sut_class = IaquaDimmableLight

    def test_property_name(self) -> None:
        super().test_property_name()
        assert self.sut.name == "aux_1"

    def test_property_label(self) -> None:
        super().test_property_label()
        assert self.sut.label == "Spa Light"

    def test_property_state(self) -> None:
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

    async def test_set_brightness_percentage_75(self) -> None:
        with patch.object(self.sut.system, "_parse_devices_response"):
            await super().test_set_brightness_percentage_75()


class TestIaquaColorLight(TestIaquaDevice, TestBaseLight):
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
        self.sut = IaquaColorLightIB(self.system, data)
        self.sut_class = IaquaColorLight

    def test_property_name(self) -> None:
        super().test_property_name()
        assert self.sut.name == "aux_1"

    def test_property_label(self) -> None:
        super().test_property_label()
        assert self.sut.label == "Pool Light"

    def test_property_manufacturer(self) -> None:
        assert self.sut.manufacturer == "Pentair"

    def test_property_model(self) -> None:
        assert self.sut.model == "Intellibrite Light"

    def test_property_is_on_false(self) -> None:
        self.sut.data["state"] = "0"
        super().test_property_is_on_false()

    def test_property_is_on_true(self) -> None:
        self.sut.data["state"] = "1"
        super().test_property_is_on_true()

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

    async def test_turn_on_noop(self) -> None:
        self.sut.data["state"] = "1"
        await super().test_turn_on_noop()

    async def test_turn_off_noop(self) -> None:
        self.sut.data["state"] = "0"
        await super().test_turn_off_noop()

    async def test_set_effect_off(self) -> None:
        with patch.object(self.sut.system, "_parse_devices_response"):
            await super().test_set_effect_off()

    async def test_set_effect_invalid_amaranth(self) -> None:
        with patch.object(self.sut.system, "_parse_devices_response"):
            await super().test_set_effect_invalid_amaranth()


class TestIaquaSetPoint(TestIaquaDevice, TestBaseNumber):
    def setUp(self) -> None:
        super().setUp()

        self.system.temp_unit = IaquaTemperatureUnit.FAHRENHEIT

        pool_set_point = {"name": "pool_set_point", "state": "86"}
        self.sut = IaquaSetPoint(self.system, pool_set_point)
        self.sut_class = IaquaSetPoint

        spa_set_point = {"name": "spa_set_point", "state": "102"}
        self.spa_set_point = IaquaSetPoint(self.system, spa_set_point)

        self.system.devices = {"pool_set_point": self.sut}

    def test_property_label(self) -> None:
        assert self.sut.label == "Pool Set Point"

    def test_property_name(self) -> None:
        assert self.sut.name == "pool_set_point"

    def test_property_state(self) -> None:
        assert self.sut.state == "86"

    def test_property_current_value(self) -> None:
        assert self.sut.current_value == 86.0

    def test_property_current_value_empty_state(self) -> None:
        self.sut.data["state"] = ""
        assert self.sut.current_value is None

    def test_property_min_value_f(self) -> None:
        self.system.temp_unit = IaquaTemperatureUnit.FAHRENHEIT
        assert self.sut.min_value == float(IAQUA_TEMP_FAHRENHEIT_LOW)

    def test_property_min_value_c(self) -> None:
        self.system.temp_unit = IaquaTemperatureUnit.CELSIUS
        assert self.sut.min_value == float(IAQUA_TEMP_CELSIUS_LOW)

    def test_property_max_value_f(self) -> None:
        self.system.temp_unit = IaquaTemperatureUnit.FAHRENHEIT
        assert self.sut.max_value == float(IAQUA_TEMP_FAHRENHEIT_HIGH)

    def test_property_max_value_c(self) -> None:
        self.system.temp_unit = IaquaTemperatureUnit.CELSIUS
        assert self.sut.max_value == float(IAQUA_TEMP_CELSIUS_HIGH)

    def test_property_unit_of_measurement_f(self) -> None:
        self.system.temp_unit = IaquaTemperatureUnit.FAHRENHEIT
        assert self.sut.unit_of_measurement == "°F"

    def test_property_unit_of_measurement_c(self) -> None:
        self.system.temp_unit = IaquaTemperatureUnit.CELSIUS
        assert self.sut.unit_of_measurement == "°C"

    def test_property_unit_of_measurement_none(self) -> None:
        self.system.temp_unit = None
        assert self.sut.unit_of_measurement is None

    def test_temperature_key_spa_present(self) -> None:
        self.system.devices["spa_set_point"] = self.spa_set_point
        assert self.spa_set_point._temperature_key == "temp1"
        assert self.sut._temperature_key == "temp2"

    def test_temperature_key_no_spa(self) -> None:
        assert self.sut._temperature_key == "temp1"

    async def test_set_value_at_min(self) -> None:
        with patch.object(self.sut.system, "_parse_home_response"):
            await super().test_set_value_at_min()

    async def test_set_value_at_max(self) -> None:
        with patch.object(self.sut.system, "_parse_home_response"):
            await super().test_set_value_at_max()

    @respx.mock
    async def test_set_value_sends_set_temps_spa_present(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        self.system.devices["spa_set_point"] = self.spa_set_point
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_home_response"):
            await self.sut.set_value(86.0)
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "temp1=102" in url
        assert "temp2=86" in url

    @respx.mock
    async def test_set_value_sends_set_temps_no_spa(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        self.system.temp_unit = IaquaTemperatureUnit.CELSIUS
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_home_response"):
            await self.sut.set_value(30.0)
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "temp1=30" in url
        assert "temp2" not in url

    def test_min_value_raises_when_temp_unit_is_none(self) -> None:
        self.system.temp_unit = None
        with pytest.raises(AqualinkStateUnavailableException):
            _ = self.sut.min_value

    def test_max_value_raises_when_temp_unit_is_none(self) -> None:
        self.system.temp_unit = None
        with pytest.raises(AqualinkStateUnavailableException):
            _ = self.sut.max_value


class TestIaquaClimate(TestIaquaDevice, TestBaseClimate):
    def setUp(self) -> None:
        super().setUp()

        self.system.temp_unit = IaquaTemperatureUnit.FAHRENHEIT

        pool_set_point = {"name": "pool_set_point", "state": "86"}
        self.pool_set_point = IaquaSetPoint(self.system, pool_set_point)

        pool_temp = {"name": "pool_temp", "state": "65"}
        self.pool_temp = IaquaSensor(self.system, pool_temp)

        pool_heater = {"name": "pool_heater", "state": "0"}
        self.pool_heater = IaquaHeater(self.system, pool_heater)

        spa_set_point = {"name": "spa_set_point", "state": "102"}
        self.spa_set_point = IaquaSetPoint(self.system, spa_set_point)

        self.system.devices = {
            "pool_set_point": self.pool_set_point,
            "pool_heater": self.pool_heater,
            "pool_temp": self.pool_temp,
        }

        self.sut = IaquaClimate(self.system, {"name": "pool_thermostat"})
        self.system.devices["pool_thermostat"] = self.sut
        self.sut_class = IaquaClimate

    def test_property_label(self) -> None:
        assert self.sut.label == "Pool Thermostat"

    def test_property_name(self) -> None:
        assert self.sut.name == "pool_thermostat"

    def test_property_state(self) -> None:
        pytest.skip("Virtual thermostat has no state field.")

    def test_property_is_on_true(self) -> None:
        self.pool_heater.data["state"] = "1"
        super().test_property_is_on_true()

    def test_property_is_on_false(self) -> None:
        self.pool_heater.data["state"] = "0"
        super().test_property_is_on_false()

    def test_property_temperature_unit(self) -> None:
        self.sut.system.temp_unit = "F"
        super().test_property_temperature_unit()

    def test_property_min_temp_f(self) -> None:
        self.sut.system.temp_unit = "F"
        super().test_property_min_temp_c()
        assert self.sut.min_temp == IAQUA_TEMP_FAHRENHEIT_LOW

    def test_property_min_temp_c(self) -> None:
        self.sut.system.temp_unit = "C"
        super().test_property_min_temp_f()
        assert self.sut.min_temp == IAQUA_TEMP_CELSIUS_LOW

    def test_property_max_temp_f(self) -> None:
        self.sut.system.temp_unit = "F"
        super().test_property_max_temp_f()
        assert self.sut.max_temp == IAQUA_TEMP_FAHRENHEIT_HIGH

    def test_property_max_temp_c(self) -> None:
        self.sut.system.temp_unit = "C"
        super().test_property_max_temp_c()
        assert self.sut.max_temp == IAQUA_TEMP_CELSIUS_HIGH

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
        with patch.object(self.sut.system, "_parse_home_response"):
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
        with patch.object(self.sut.system, "_parse_home_response"):
            await super().test_turn_off_noop()

    async def test_set_temperature_86f(self) -> None:
        self.system.devices["spa_set_point"] = self.spa_set_point
        with patch.object(self.sut.system, "_parse_home_response"):
            await super().test_set_temperature_86f()
        assert len(self.respx_calls) == 1
        url = str(self.respx_calls[0].request.url)
        assert "temp1=102" in url
        assert "temp2=86" in url

    async def test_set_temperature_30c(self) -> None:
        self.system.temp_unit = IaquaTemperatureUnit.CELSIUS
        with patch.object(self.sut.system, "_parse_home_response"):
            await super().test_set_temperature_30c()
        assert len(self.respx_calls) == 1
        url = str(self.respx_calls[0].request.url)
        assert "temp1=30" in url
        assert "temp2" not in url

    def test_temperature_unit_raises_when_temp_unit_is_none(self) -> None:
        self.sut.system.temp_unit = None
        with pytest.raises(AqualinkStateUnavailableException):
            _ = self.sut.temperature_unit
