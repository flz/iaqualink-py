from __future__ import annotations

from unittest.mock import patch

import pytest
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

from ...conftest import dotstar, resp_200
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


def test_device_state() -> None:
    """IaquaDevice.state returns raw data["state"] string."""
    system = make_system()
    dev = IaquaDevice(system, {**IAQUA_DEVICE_DATA})
    assert dev.state == "42"


class TestIaquaSensor:
    def test_property_value(self) -> None:
        sut = IaquaSensor(make_system(), {**IAQUA_SENSOR_DATA})
        assert sut.value == "42"


class TestIaquaBinarySensor:
    def test_is_on_false(self) -> None:
        sut = IaquaBinarySensor(
            make_system(), {**IAQUA_BINARY_SENSOR_OFF_DATA, "state": "0"}
        )
        assert sut.is_on is False

    def test_is_on_true(self) -> None:
        sut = IaquaBinarySensor(
            make_system(), {**IAQUA_BINARY_SENSOR_OFF_DATA, "state": "1"}
        )
        assert sut.is_on is True


class TestIaquaPresenceSensor:
    def test_is_on_true(self) -> None:
        sut = IaquaPresenceSensor(
            make_system(), {"name": "is_icl_present", "state": "present"}
        )
        assert sut.is_on is True

    def test_is_on_false(self) -> None:
        sut = IaquaPresenceSensor(
            make_system(), {"name": "is_icl_present", "state": "absent"}
        )
        assert sut.is_on is False

    def test_is_on_false_empty(self) -> None:
        sut = IaquaPresenceSensor(
            make_system(), {"name": "is_icl_present", "state": ""}
        )
        assert sut.is_on is False


class TestIaquaSwitch:
    async def test_turn_on(self, respx_mock: respx.router.MockRouter) -> None:
        sut = IaquaSwitch(
            make_system(), {**IAQUA_SWITCH_OFF_DATA, "state": "0"}
        )
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_home_response"):
            await sut.turn_on()
        assert len(respx_mock.calls) > 0

    async def test_turn_off(self, respx_mock: respx.router.MockRouter) -> None:
        sut = IaquaSwitch(
            make_system(), {**IAQUA_SWITCH_OFF_DATA, "state": "1"}
        )
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_home_response"):
            await sut.turn_off()
        assert len(respx_mock.calls) > 0


class TestIaquaHeater:
    def test_is_on_false(self) -> None:
        sut = IaquaHeater(
            make_system(), {**IAQUA_HEATER_OFF_DATA, "state": "0"}
        )
        assert sut.is_on is False

    def test_is_on_true(self) -> None:
        sut = IaquaHeater(
            make_system(), {**IAQUA_HEATER_OFF_DATA, "state": "1"}
        )
        assert sut.is_on is True

    def test_is_on_enabled(self) -> None:
        """State "3" (enabled/waiting) is treated as on."""
        sut = IaquaHeater(
            make_system(), {**IAQUA_HEATER_OFF_DATA, "state": "3"}
        )
        assert sut.is_on is True

    async def test_turn_on(self, respx_mock: respx.router.MockRouter) -> None:
        sut = IaquaHeater(
            make_system(), {**IAQUA_HEATER_OFF_DATA, "state": "0"}
        )
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_home_response"):
            await sut.turn_on()
        assert len(respx_mock.calls) > 0

    async def test_turn_off(self, respx_mock: respx.router.MockRouter) -> None:
        sut = IaquaHeater(
            make_system(), {**IAQUA_HEATER_OFF_DATA, "state": "1"}
        )
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_home_response"):
            await sut.turn_off()
        assert len(respx_mock.calls) > 0


class TestIaquaOneTouchSwitch:
    def test_property_label(self) -> None:
        sut = IaquaOneTouchSwitch(make_system(), {**IAQUA_ONETOUCH_OFF_DATA})
        assert sut.label == "Morning Scene"

    async def test_turn_on(self, respx_mock: respx.router.MockRouter) -> None:
        sut = IaquaOneTouchSwitch(
            make_system(), {**IAQUA_ONETOUCH_OFF_DATA, "state": "0"}
        )
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_onetouch_response"):
            await sut.turn_on()
        assert len(respx_mock.calls) > 0

    async def test_turn_off(self, respx_mock: respx.router.MockRouter) -> None:
        sut = IaquaOneTouchSwitch(
            make_system(), {**IAQUA_ONETOUCH_OFF_DATA, "state": "1"}
        )
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_onetouch_response"):
            await sut.turn_off()
        assert len(respx_mock.calls) > 0


class TestIaquaAuxSwitch:
    async def test_turn_on(self, respx_mock: respx.router.MockRouter) -> None:
        sut = IaquaAuxSwitch(
            make_system(), {**IAQUA_AUX_SWITCH_OFF_DATA, "state": "0"}
        )
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_devices_response"):
            await sut.turn_on()
        assert len(respx_mock.calls) > 0

    async def test_turn_off(self, respx_mock: respx.router.MockRouter) -> None:
        sut = IaquaAuxSwitch(
            make_system(), {**IAQUA_AUX_SWITCH_OFF_DATA, "state": "1"}
        )
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_devices_response"):
            await sut.turn_off()
        assert len(respx_mock.calls) > 0


class TestIaquaLightSwitch:
    def test_brightness_is_none(self) -> None:
        sut = IaquaLightSwitch(make_system(), {**IAQUA_LIGHT_SWITCH_OFF_DATA})
        assert sut.brightness_percentage is None

    def test_effect_is_none(self) -> None:
        sut = IaquaLightSwitch(make_system(), {**IAQUA_LIGHT_SWITCH_OFF_DATA})
        assert sut.effect is None

    async def test_turn_on(self, respx_mock: respx.router.MockRouter) -> None:
        sut = IaquaLightSwitch(
            make_system(), {**IAQUA_LIGHT_SWITCH_OFF_DATA, "state": "0"}
        )
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_devices_response"):
            await sut.turn_on()
        assert len(respx_mock.calls) > 0

    async def test_turn_off(self, respx_mock: respx.router.MockRouter) -> None:
        sut = IaquaLightSwitch(
            make_system(), {**IAQUA_LIGHT_SWITCH_OFF_DATA, "state": "1"}
        )
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_devices_response"):
            await sut.turn_off()
        assert len(respx_mock.calls) > 0


class TestIaquaDimmableLight:
    """iAqua dimmable light — brightness support, state+subtype logic."""

    def test_property_label(self) -> None:
        sut = IaquaDimmableLight(
            make_system(), {**IAQUA_DIMMABLE_LIGHT_ON_DATA}
        )
        assert sut.label == "Spa Light"

    def test_is_on_true(self) -> None:
        sut = IaquaDimmableLight(
            make_system(),
            {**IAQUA_DIMMABLE_LIGHT_ON_DATA, "state": "1", "subtype": "100"},
        )
        assert sut.is_on is True

    def test_is_on_false(self) -> None:
        sut = IaquaDimmableLight(
            make_system(),
            {**IAQUA_DIMMABLE_LIGHT_ON_DATA, "state": "0", "subtype": "0"},
        )
        assert sut.is_on is False

    def test_supports_brightness(self) -> None:
        sut = IaquaDimmableLight(
            make_system(), {**IAQUA_DIMMABLE_LIGHT_ON_DATA}
        )
        assert sut.supports_brightness is True

    def test_supports_effect(self) -> None:
        sut = IaquaDimmableLight(
            make_system(), {**IAQUA_DIMMABLE_LIGHT_ON_DATA}
        )
        assert sut.supports_effect is False

    async def test_turn_on(self, respx_mock: respx.router.MockRouter) -> None:
        sut = IaquaDimmableLight(
            make_system(),
            {**IAQUA_DIMMABLE_LIGHT_ON_DATA, "state": "0", "subtype": "0"},
        )
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_devices_response"):
            await sut.turn_on()
        assert len(respx_mock.calls) > 0

    async def test_turn_off(self, respx_mock: respx.router.MockRouter) -> None:
        sut = IaquaDimmableLight(
            make_system(),
            {**IAQUA_DIMMABLE_LIGHT_ON_DATA, "state": "1", "subtype": "100"},
        )
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_devices_response"):
            await sut.turn_off()
        assert len(respx_mock.calls) > 0

    async def test_set_brightness(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        sut = IaquaDimmableLight(
            make_system(), {**IAQUA_DIMMABLE_LIGHT_ON_DATA}
        )
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_devices_response"):
            await sut.set_brightness_percentage(75)
        assert len(respx_mock.calls) > 0


class TestIaquaColorLight:
    """iAqua color light — effect support, Pentair manufacturer/model override."""

    def test_property_label(self) -> None:
        sut = IaquaColorLightIB(make_system(), {**IAQUA_COLOR_LIGHT_OFF_DATA})
        assert sut.label == "Pool Light"

    def test_property_manufacturer(self) -> None:
        sut = IaquaColorLightIB(make_system(), {**IAQUA_COLOR_LIGHT_OFF_DATA})
        assert sut.manufacturer == "Pentair"

    def test_property_model(self) -> None:
        sut = IaquaColorLightIB(make_system(), {**IAQUA_COLOR_LIGHT_OFF_DATA})
        assert sut.model == "Intellibrite Light"

    def test_supports_brightness(self) -> None:
        sut = IaquaColorLightIB(make_system(), {**IAQUA_COLOR_LIGHT_OFF_DATA})
        assert sut.supports_brightness is False

    def test_supports_effect(self) -> None:
        sut = IaquaColorLightIB(make_system(), {**IAQUA_COLOR_LIGHT_OFF_DATA})
        assert sut.supports_effect is True

    async def test_turn_on(self, respx_mock: respx.router.MockRouter) -> None:
        sut = IaquaColorLightIB(
            make_system(), {**IAQUA_COLOR_LIGHT_OFF_DATA, "state": "0"}
        )
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_devices_response"):
            await sut.turn_on()
        assert len(respx_mock.calls) > 0

    async def test_turn_off(self, respx_mock: respx.router.MockRouter) -> None:
        sut = IaquaColorLightIB(
            make_system(), {**IAQUA_COLOR_LIGHT_OFF_DATA, "state": "1"}
        )
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_devices_response"):
            await sut.turn_off()
        assert len(respx_mock.calls) > 0

    async def test_set_effect(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        sut = IaquaColorLightIB(make_system(), {**IAQUA_COLOR_LIGHT_OFF_DATA})
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_devices_response"):
            await sut.set_effect("Off")
        assert len(respx_mock.calls) > 0


def _make_setpoint():
    """Return (system, pool_set_point, spa_set_point) wired together."""
    system = make_system()
    system.temp_unit = IaquaTemperatureUnit.FAHRENHEIT
    sut = IaquaSetPoint(system, {**IAQUA_POOL_SET_POINT_DATA})
    spa_set_point = IaquaSetPoint(
        system, {"name": "spa_set_point", "state": "102"}
    )
    system.devices = {"pool_set_point": sut}
    return system, sut, spa_set_point


class TestIaquaSetPoint:
    """iAqua set point — temp key logic, wire-protocol URL verification."""

    def test_property_label(self) -> None:
        _, sut, _ = _make_setpoint()
        assert sut.label == "Pool Set Point"

    def test_property_current_value(self) -> None:
        _, sut, _ = _make_setpoint()
        assert sut.current_value == 86.0

    def test_property_current_value_empty_state(self) -> None:
        _, sut, _ = _make_setpoint()
        sut.data["state"] = ""
        assert sut.current_value is None

    def test_property_min_value_f(self) -> None:
        system, sut, _ = _make_setpoint()
        system.temp_unit = IaquaTemperatureUnit.FAHRENHEIT
        assert sut.min_value == float(IAQUA_TEMP_FAHRENHEIT_LOW)

    def test_property_min_value_c(self) -> None:
        system, sut, _ = _make_setpoint()
        system.temp_unit = IaquaTemperatureUnit.CELSIUS
        assert sut.min_value == float(IAQUA_TEMP_CELSIUS_LOW)

    def test_property_max_value_f(self) -> None:
        system, sut, _ = _make_setpoint()
        system.temp_unit = IaquaTemperatureUnit.FAHRENHEIT
        assert sut.max_value == float(IAQUA_TEMP_FAHRENHEIT_HIGH)

    def test_property_max_value_c(self) -> None:
        system, sut, _ = _make_setpoint()
        system.temp_unit = IaquaTemperatureUnit.CELSIUS
        assert sut.max_value == float(IAQUA_TEMP_CELSIUS_HIGH)

    def test_property_unit_of_measurement_f(self) -> None:
        system, sut, _ = _make_setpoint()
        system.temp_unit = IaquaTemperatureUnit.FAHRENHEIT
        assert sut.unit_of_measurement == "°F"

    def test_property_unit_of_measurement_c(self) -> None:
        system, sut, _ = _make_setpoint()
        system.temp_unit = IaquaTemperatureUnit.CELSIUS
        assert sut.unit_of_measurement == "°C"

    def test_property_unit_of_measurement_none(self) -> None:
        system, sut, _ = _make_setpoint()
        system.temp_unit = None
        assert sut.unit_of_measurement is None

    def test_temperature_key_spa_present(self) -> None:
        system, sut, spa_set_point = _make_setpoint()
        system.devices["spa_set_point"] = spa_set_point
        assert spa_set_point._temperature_key == "temp1"
        assert sut._temperature_key == "temp2"

    def test_temperature_key_no_spa(self) -> None:
        _, sut, _ = _make_setpoint()
        assert sut._temperature_key == "temp1"

    async def test_set_value_sends_set_temps_spa_present(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        system, sut, spa_set_point = _make_setpoint()
        system.devices["spa_set_point"] = spa_set_point
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_home_response"):
            await sut.set_value(86.0)
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "temp1=102" in url
        assert "temp2=86" in url

    async def test_set_value_sends_set_temps_no_spa(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        system, sut, _ = _make_setpoint()
        system.temp_unit = IaquaTemperatureUnit.CELSIUS
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_home_response"):
            await sut.set_value(30.0)
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "temp1=30" in url
        assert "temp2" not in url

    def test_min_value_raises_when_temp_unit_is_none(self) -> None:
        system, sut, _ = _make_setpoint()
        system.temp_unit = None
        with pytest.raises(AqualinkStateUnavailableException):
            _ = sut.min_value

    def test_max_value_raises_when_temp_unit_is_none(self) -> None:
        system, sut, _ = _make_setpoint()
        system.temp_unit = None
        with pytest.raises(AqualinkStateUnavailableException):
            _ = sut.max_value


def _make_climate():
    """Return (system, pool_set_point, pool_temp, pool_heater, spa_set_point, sut)."""
    system = make_system()
    system.temp_unit = IaquaTemperatureUnit.FAHRENHEIT
    pool_set_point = IaquaSetPoint(system, {**IAQUA_POOL_SET_POINT_DATA})
    pool_temp = IaquaSensor(system, {**IAQUA_POOL_TEMP_DATA})
    pool_heater = IaquaHeater(system, {**IAQUA_HEATER_OFF_DATA})
    spa_set_point = IaquaSetPoint(
        system, {"name": "spa_set_point", "state": "102"}
    )
    system.devices = {
        "pool_set_point": pool_set_point,
        "pool_heater": pool_heater,
        "pool_temp": pool_temp,
    }
    sut = IaquaClimate(system, {**IAQUA_CLIMATE_DATA})
    system.devices["pool_thermostat"] = sut
    return system, pool_set_point, pool_temp, pool_heater, spa_set_point, sut


class TestIaquaClimate:
    """iAqua climate — heater state, temp unit, wire-protocol URL params."""

    def test_property_label(self) -> None:
        *_, sut = _make_climate()
        assert sut.label == "Pool Thermostat"

    def test_property_state_raises(self) -> None:
        *_, sut = _make_climate()
        with pytest.raises(AqualinkOperationNotSupportedException):
            _ = sut.state

    def test_is_on_from_heater(self) -> None:
        system, _, _, pool_heater, _, sut = _make_climate()
        pool_heater.data["state"] = "1"
        assert sut.is_on is True
        pool_heater.data["state"] = "0"
        assert sut.is_on is False

    def test_temperature_unit(self) -> None:
        system, *_, sut = _make_climate()
        system.temp_unit = "F"
        assert sut.temperature_unit == "F"

    def test_min_temp_f(self) -> None:
        system, *_, sut = _make_climate()
        system.temp_unit = "F"
        assert sut.min_temp == IAQUA_TEMP_FAHRENHEIT_LOW

    def test_min_temp_c(self) -> None:
        system, *_, sut = _make_climate()
        system.temp_unit = "C"
        assert sut.min_temp == IAQUA_TEMP_CELSIUS_LOW

    def test_max_temp_f(self) -> None:
        system, *_, sut = _make_climate()
        system.temp_unit = "F"
        assert sut.max_temp == IAQUA_TEMP_FAHRENHEIT_HIGH

    def test_max_temp_c(self) -> None:
        system, *_, sut = _make_climate()
        system.temp_unit = "C"
        assert sut.max_temp == IAQUA_TEMP_CELSIUS_HIGH

    def test_current_temperature(self) -> None:
        *_, sut = _make_climate()
        assert sut.current_temperature == "65"

    def test_target_temperature(self) -> None:
        *_, sut = _make_climate()
        assert sut.target_temperature == "86"

    async def test_turn_on_url(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        system, _, _, pool_heater, _, sut = _make_climate()
        pool_heater.data["state"] = "0"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_home_response"):
            await sut.turn_on()
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "set_pool_heater" in url

    async def test_turn_off_url(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        system, _, _, pool_heater, _, sut = _make_climate()
        pool_heater.data["state"] = "1"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_home_response"):
            await sut.turn_off()
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "set_pool_heater" in url

    async def test_set_temperature_url_spa_present(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        system, _, _, _, spa_set_point, sut = _make_climate()
        system.devices["spa_set_point"] = spa_set_point
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_home_response"):
            await sut.set_temperature(86)
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "temp1=102" in url
        assert "temp2=86" in url

    async def test_set_temperature_url_celsius(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        system, *_, sut = _make_climate()
        system.temp_unit = IaquaTemperatureUnit.CELSIUS
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_home_response"):
            await sut.set_temperature(30)
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "temp1=30" in url
        assert "temp2" not in url

    def test_temperature_unit_raises_when_none(self) -> None:
        system, *_, sut = _make_climate()
        system.temp_unit = None
        with pytest.raises(AqualinkStateUnavailableException):
            _ = sut.temperature_unit
