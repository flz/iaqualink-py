from __future__ import annotations

import copy
from unittest.mock import patch

import pytest
import respx
import respx.router

from iaqualink.exception import (
    AqualinkOperationNotSupportedException,
    AqualinkStateUnavailableException,
)
from iaqualink.systems.iaqua.device import (
    IAQUA_TEMP_CELSIUS_HIGH,
    IAQUA_TEMP_CELSIUS_LOW,
    IAQUA_TEMP_FAHRENHEIT_HIGH,
    IAQUA_TEMP_FAHRENHEIT_LOW,
    IaquaAuxSwitch,
    IaquaBinarySensor,
    IaquaClimate,
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

from ...conftest import TestBase, dotstar, resp_200
from .factories import (
    IAQUA_AUX_SWITCH_OFF_DATA,
    IAQUA_BINARY_SENSOR_OFF_DATA,
    IAQUA_CLIMATE_DATA,
    IAQUA_COLOR_LIGHT_OFF_DATA,
    IAQUA_DEVICE_DATA,
    IAQUA_DIMMABLE_LIGHT_ON_DATA,
    IAQUA_HEATER_OFF_DATA,
    IAQUA_LIGHT_SWITCH_OFF_DATA,
    IAQUA_ONETOUCH_OFF_DATA,
    IAQUA_POOL_SET_POINT_DATA,
    IAQUA_POOL_TEMP_DATA,
    IAQUA_SENSOR_DATA,
    IAQUA_SWITCH_OFF_DATA,
    make_system,
)


class TestIaquaDevice(TestBase):
    """iAqua device — equality, name, state, manufacturer/model."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.sut = IaquaDevice(self.system, {**IAQUA_DEVICE_DATA})

    def test_equal(self) -> None:
        assert self.sut == self.sut

    def test_not_equal(self) -> None:
        obj2 = copy.deepcopy(self.sut)
        obj2.data["name"] = "device_2"
        assert self.sut != obj2

    def test_not_equal_different_type(self) -> None:
        assert (self.sut == {}) is False

    def test_property_name(self) -> None:
        assert self.sut.name == "device"

    def test_property_state(self) -> None:
        assert self.sut.state == "42"

    def test_property_manufacturer(self) -> None:
        assert self.sut.manufacturer == "Jandy"

    def test_property_model(self) -> None:
        assert self.sut.model == "Device"


class TestIaquaSensor(TestBase):
    """iAqua sensor — value from state."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.sut = IaquaSensor(self.system, {**IAQUA_SENSOR_DATA})

    def test_property_value(self) -> None:
        assert self.sut.value == "42"


class TestIaquaBinarySensor(TestBase):
    """iAqua binary sensor — state "0"/"1" mapping."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.sut = IaquaBinarySensor(
            self.system, {**IAQUA_BINARY_SENSOR_OFF_DATA}
        )

    def test_is_on_false(self) -> None:
        self.sut.data["state"] = "0"
        assert self.sut.is_on is False

    def test_is_on_true(self) -> None:
        self.sut.data["state"] = "1"
        assert self.sut.is_on is True


class TestIaquaPresenceSensor(TestBase):
    """iAqua presence sensor — "present"/"absent" mapping."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.sut = IaquaPresenceSensor(
            self.system, {"name": "is_icl_present", "state": "present"}
        )

    def test_is_on_true(self) -> None:
        self.sut.data["state"] = "present"
        assert self.sut.is_on is True

    def test_is_on_false(self) -> None:
        self.sut.data["state"] = "absent"
        assert self.sut.is_on is False

    def test_is_on_false_empty(self) -> None:
        self.sut.data["state"] = ""
        assert self.sut.is_on is False


class TestIaquaSwitch(TestBase):
    """iAqua switch — turn_on/off patches _parse_home_response."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.sut = IaquaSwitch(self.system, {**IAQUA_SWITCH_OFF_DATA})

    @respx.mock
    async def test_turn_on(self, respx_mock: respx.router.MockRouter) -> None:
        self.sut.data["state"] = "0"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_home_response"):
            await self.sut.turn_on()
        assert len(respx_mock.calls) > 0

    @respx.mock
    async def test_turn_off(self, respx_mock: respx.router.MockRouter) -> None:
        self.sut.data["state"] = "1"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_home_response"):
            await self.sut.turn_off()
        assert len(respx_mock.calls) > 0


class TestIaquaHeater(TestBase):
    """iAqua heater — state "3" also means on."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.sut = IaquaHeater(self.system, {**IAQUA_HEATER_OFF_DATA})

    def test_is_on_false(self) -> None:
        self.sut.data["state"] = "0"
        assert self.sut.is_on is False

    def test_is_on_true(self) -> None:
        self.sut.data["state"] = "1"
        assert self.sut.is_on is True

    def test_is_on_enabled(self) -> None:
        self.sut.data["state"] = "3"
        assert self.sut.is_on is True

    @respx.mock
    async def test_turn_on(self, respx_mock: respx.router.MockRouter) -> None:
        self.sut.data["state"] = "0"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_home_response"):
            await self.sut.turn_on()
        assert len(respx_mock.calls) > 0

    @respx.mock
    async def test_turn_off(self, respx_mock: respx.router.MockRouter) -> None:
        self.sut.data["state"] = "1"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_home_response"):
            await self.sut.turn_off()
        assert len(respx_mock.calls) > 0


class TestIaquaOneTouchSwitch(TestBase):
    """iAqua OneTouch switch — patches _parse_onetouch_response, custom label."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.sut = IaquaOneTouchSwitch(self.system, {**IAQUA_ONETOUCH_OFF_DATA})

    def test_property_label(self) -> None:
        assert self.sut.label == "Morning Scene"

    @respx.mock
    async def test_turn_on(self, respx_mock: respx.router.MockRouter) -> None:
        self.sut.data["state"] = "0"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_onetouch_response"):
            await self.sut.turn_on()
        assert len(respx_mock.calls) > 0

    @respx.mock
    async def test_turn_off(self, respx_mock: respx.router.MockRouter) -> None:
        self.sut.data["state"] = "1"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_onetouch_response"):
            await self.sut.turn_off()
        assert len(respx_mock.calls) > 0


class TestIaquaAuxSwitch(TestBase):
    """iAqua aux switch — patches _parse_devices_response."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.sut = IaquaAuxSwitch(self.system, {**IAQUA_AUX_SWITCH_OFF_DATA})

    @respx.mock
    async def test_turn_on(self, respx_mock: respx.router.MockRouter) -> None:
        self.sut.data["state"] = "0"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_devices_response"):
            await self.sut.turn_on()
        assert len(respx_mock.calls) > 0

    @respx.mock
    async def test_turn_off(self, respx_mock: respx.router.MockRouter) -> None:
        self.sut.data["state"] = "1"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_devices_response"):
            await self.sut.turn_off()
        assert len(respx_mock.calls) > 0


class TestIaquaLightSwitch(TestBase):
    """iAqua light switch — no brightness, no effect."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.sut = IaquaLightSwitch(
            self.system, {**IAQUA_LIGHT_SWITCH_OFF_DATA}
        )

    def test_brightness_is_none(self) -> None:
        assert self.sut.brightness_percentage is None

    def test_effect_is_none(self) -> None:
        assert self.sut.effect is None

    @respx.mock
    async def test_turn_on(self, respx_mock: respx.router.MockRouter) -> None:
        self.sut.data["state"] = "0"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_devices_response"):
            await self.sut.turn_on()
        assert len(respx_mock.calls) > 0

    @respx.mock
    async def test_turn_off(self, respx_mock: respx.router.MockRouter) -> None:
        self.sut.data["state"] = "1"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_devices_response"):
            await self.sut.turn_off()
        assert len(respx_mock.calls) > 0


class TestIaquaDimmableLight(TestBase):
    """iAqua dimmable light — brightness support, state+subtype logic."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.sut = IaquaDimmableLight(
            self.system, {**IAQUA_DIMMABLE_LIGHT_ON_DATA}
        )

    def test_property_label(self) -> None:
        assert self.sut.label == "Spa Light"

    def test_is_on_true(self) -> None:
        self.sut.data["state"] = "1"
        self.sut.data["subtype"] = "100"
        assert self.sut.is_on is True

    def test_is_on_false(self) -> None:
        self.sut.data["state"] = "0"
        self.sut.data["subtype"] = "0"
        assert self.sut.is_on is False

    def test_supports_brightness(self) -> None:
        assert self.sut.supports_brightness is True

    def test_supports_effect(self) -> None:
        assert self.sut.supports_effect is False

    @respx.mock
    async def test_turn_on(self, respx_mock: respx.router.MockRouter) -> None:
        self.sut.data["state"] = "0"
        self.sut.data["subtype"] = "0"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_devices_response"):
            await self.sut.turn_on()
        assert len(respx_mock.calls) > 0

    @respx.mock
    async def test_turn_off(self, respx_mock: respx.router.MockRouter) -> None:
        self.sut.data["state"] = "1"
        self.sut.data["subtype"] = "100"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_devices_response"):
            await self.sut.turn_off()
        assert len(respx_mock.calls) > 0

    @respx.mock
    async def test_set_brightness(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_devices_response"):
            await self.sut.set_brightness_percentage(75)
        assert len(respx_mock.calls) > 0


class TestIaquaColorLight(TestBase):
    """iAqua color light — effect support, Pentair manufacturer/model."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.sut = IaquaColorLightIB(
            self.system, {**IAQUA_COLOR_LIGHT_OFF_DATA}
        )

    def test_property_label(self) -> None:
        assert self.sut.label == "Pool Light"

    def test_property_manufacturer(self) -> None:
        assert self.sut.manufacturer == "Pentair"

    def test_property_model(self) -> None:
        assert self.sut.model == "Intellibrite Light"

    def test_supports_brightness(self) -> None:
        assert self.sut.supports_brightness is False

    def test_supports_effect(self) -> None:
        assert self.sut.supports_effect is True

    @respx.mock
    async def test_turn_on(self, respx_mock: respx.router.MockRouter) -> None:
        self.sut.data["state"] = "0"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_devices_response"):
            await self.sut.turn_on()
        assert len(respx_mock.calls) > 0

    @respx.mock
    async def test_turn_off(self, respx_mock: respx.router.MockRouter) -> None:
        self.sut.data["state"] = "1"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_devices_response"):
            await self.sut.turn_off()
        assert len(respx_mock.calls) > 0

    @respx.mock
    async def test_set_effect(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_devices_response"):
            await self.sut.set_effect("Off")
        assert len(respx_mock.calls) > 0


class TestIaquaSetPoint(TestBase):
    """iAqua set point — temp key logic, wire-protocol URL verification."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.system.temp_unit = IaquaTemperatureUnit.FAHRENHEIT

        self.sut = IaquaSetPoint(self.system, {**IAQUA_POOL_SET_POINT_DATA})

        spa_set_point = {"name": "spa_set_point", "state": "102"}
        self.spa_set_point = IaquaSetPoint(self.system, spa_set_point)

        self.system.devices = {"pool_set_point": self.sut}

    def test_property_label(self) -> None:
        assert self.sut.label == "Pool Set Point"

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


class TestIaquaClimate(TestBase):
    """iAqua climate — heater state, temp unit, wire-protocol URL params."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.system.temp_unit = IaquaTemperatureUnit.FAHRENHEIT

        self.pool_set_point = IaquaSetPoint(
            self.system, {**IAQUA_POOL_SET_POINT_DATA}
        )
        self.pool_temp = IaquaSensor(self.system, {**IAQUA_POOL_TEMP_DATA})
        self.pool_heater = IaquaHeater(self.system, {**IAQUA_HEATER_OFF_DATA})

        spa_set_point = {"name": "spa_set_point", "state": "102"}
        self.spa_set_point = IaquaSetPoint(self.system, spa_set_point)

        self.system.devices = {
            "pool_set_point": self.pool_set_point,
            "pool_heater": self.pool_heater,
            "pool_temp": self.pool_temp,
        }

        self.sut = IaquaClimate(self.system, {**IAQUA_CLIMATE_DATA})
        self.system.devices["pool_thermostat"] = self.sut

    def test_property_label(self) -> None:
        assert self.sut.label == "Pool Thermostat"

    def test_property_state_raises(self) -> None:
        with pytest.raises(AqualinkOperationNotSupportedException):
            _ = self.sut.state

    def test_is_on_from_heater(self) -> None:
        self.pool_heater.data["state"] = "1"
        assert self.sut.is_on is True
        self.pool_heater.data["state"] = "0"
        assert self.sut.is_on is False

    def test_temperature_unit(self) -> None:
        self.system.temp_unit = "F"
        assert self.sut.temperature_unit == "F"

    def test_min_temp_f(self) -> None:
        self.system.temp_unit = "F"
        assert self.sut.min_temp == IAQUA_TEMP_FAHRENHEIT_LOW

    def test_min_temp_c(self) -> None:
        self.system.temp_unit = "C"
        assert self.sut.min_temp == IAQUA_TEMP_CELSIUS_LOW

    def test_max_temp_f(self) -> None:
        self.system.temp_unit = "F"
        assert self.sut.max_temp == IAQUA_TEMP_FAHRENHEIT_HIGH

    def test_max_temp_c(self) -> None:
        self.system.temp_unit = "C"
        assert self.sut.max_temp == IAQUA_TEMP_CELSIUS_HIGH

    def test_current_temperature(self) -> None:
        assert self.sut.current_temperature == "65"

    def test_target_temperature(self) -> None:
        assert self.sut.target_temperature == "86"

    @respx.mock
    async def test_turn_on_url(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        self.pool_heater.data["state"] = "0"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_home_response"):
            await self.sut.turn_on()
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "set_pool_heater" in url

    @respx.mock
    async def test_turn_off_url(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        self.pool_heater.data["state"] = "1"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_home_response"):
            await self.sut.turn_off()
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "set_pool_heater" in url

    @respx.mock
    async def test_set_temperature_url_spa_present(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        self.system.devices["spa_set_point"] = self.spa_set_point
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_home_response"):
            await self.sut.set_temperature(86)
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "temp1=102" in url
        assert "temp2=86" in url

    @respx.mock
    async def test_set_temperature_url_celsius(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        self.system.temp_unit = IaquaTemperatureUnit.CELSIUS
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(self.sut.system, "_parse_home_response"):
            await self.sut.set_temperature(30)
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "temp1=30" in url
        assert "temp2" not in url

    def test_temperature_unit_raises_when_none(self) -> None:
        self.sut.system.temp_unit = None
        with pytest.raises(AqualinkStateUnavailableException):
            _ = self.sut.temperature_unit
