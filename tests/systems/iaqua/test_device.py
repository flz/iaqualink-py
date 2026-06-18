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
    ICL_CUSTOM_COLOR_ID,
    ICL_EFFECTS,
    IaquaAuxSwitch,
    IaquaBinarySensor,
    IaquaClimate,
    IaquaColorLightIB,
    IaquaDevice,
    IaquaDimmableLight,
    IaquaHeater,
    IaquaIclLight,
    IaquaLightSwitch,
    IaquaOneTouchSwitch,
    IaquaPresenceSensor,
    IaquaSensor,
    IaquaSetPoint,
    IaquaSwcBoostPauseButton,
    IaquaSwcBoostResumeButton,
    IaquaSwcBoostStartButton,
    IaquaSwcBoostStopButton,
    IaquaSwcSetPoint,
    IaquaSwitch,
    IaquaVSPump,
    IaquaZoneStatus,
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
    IAQUA_SWC_POOL_SET_POINT_DATA,
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


# ---------------------------------------------------------------------------
# ICL data / helpers
# ---------------------------------------------------------------------------

_ICL_ZONE_DATA: dict = {
    "zoneId": "1",
    "zoneName": "Pool Light",
    "zoneStatus": "on",
    "zoneColor": "6",
    "zoneColorVal": "Emerald Green",
    "dim_level": "100",
    "red_val": "255",
    "green_val": "128",
    "blue_val": "64",
    "white_val": "0",
}


def _make_icl_light() -> IaquaIclLight:
    return IaquaIclLight(make_system(), {**_ICL_ZONE_DATA})


class TestIaquaIclLight:
    """Tests for IaquaIclLight (IntelliCenter Light) device."""

    def test_property_name(self) -> None:
        sut = _make_icl_light()
        assert sut.name == "icl_zone_1"

    def test_property_label(self) -> None:
        sut = _make_icl_light()
        assert sut.label == "Pool Light"

    def test_property_label_fallback(self) -> None:
        sut = _make_icl_light()
        sut.data["zoneName"] = ""
        assert sut.label == "Light Zone 1"

    def test_property_state(self) -> None:
        sut = _make_icl_light()
        assert sut.state == IaquaZoneStatus.ON

    def test_property_state_off(self) -> None:
        sut = _make_icl_light()
        sut.data["zoneStatus"] = "off"
        assert sut.state == IaquaZoneStatus.OFF

    def test_property_is_on_true(self) -> None:
        sut = _make_icl_light()
        assert sut.is_on is True

    def test_property_is_on_false(self) -> None:
        sut = _make_icl_light()
        sut.data["zoneStatus"] = "off"
        assert sut.is_on is False

    def test_property_manufacturer(self) -> None:
        sut = _make_icl_light()
        assert sut.manufacturer == "Jandy"

    def test_property_model(self) -> None:
        sut = _make_icl_light()
        assert sut.model == "IntelliCenter Light"

    def test_property_zone_id(self) -> None:
        sut = _make_icl_light()
        assert sut._zone_id == 1

    def test_property_brightness_percentage(self) -> None:
        sut = _make_icl_light()
        assert sut.brightness_percentage == 100

    def test_property_brightness_percentage_absent(self) -> None:
        sut = _make_icl_light()
        del sut.data["dim_level"]
        assert sut.brightness_percentage is None

    def test_property_supports_brightness(self) -> None:
        sut = _make_icl_light()
        assert sut.supports_brightness is True

    def test_property_effect(self) -> None:
        sut = _make_icl_light()
        assert sut.effect == "Emerald Green"

    def test_property_supports_effect(self) -> None:
        sut = _make_icl_light()
        assert sut.supports_effect is True

    def test_property_color_id(self) -> None:
        sut = _make_icl_light()
        assert sut._color_id == 6

    def test_property_effect_color_id_zero(self) -> None:
        sut = _make_icl_light()
        sut.data["zoneColor"] = "0"
        sut.data["zoneColorVal"] = "off"
        assert sut.effect is None

    def test_property_rgbw(self) -> None:
        sut = _make_icl_light()
        assert sut.rgbw == (255, 128, 64, 0)

    def test_property_supports_rgbw(self) -> None:
        sut = _make_icl_light()
        assert sut.supports_rgbw is True

    def test_property_effect_list(self) -> None:
        sut = _make_icl_light()
        assert sut.effect_list == list(ICL_EFFECTS)
        assert "Emerald Green" in sut.effect_list

    async def test_turn_on(self, respx_mock: respx.router.MockRouter) -> None:
        sut = _make_icl_light()
        sut.data["zoneStatus"] = "off"
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_icl_info_response"):
            await sut.turn_on()
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "onoff_iclzone" in url
        assert "zone_id=1" in url
        assert "on_off_action=on" in url

    async def test_turn_on_noop(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        sut = _make_icl_light()
        respx_mock.route(dotstar).mock(resp_200)
        await sut.turn_on()
        assert len(respx_mock.calls) == 0

    async def test_turn_off(self, respx_mock: respx.router.MockRouter) -> None:
        sut = _make_icl_light()
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_icl_info_response"):
            await sut.turn_off()
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "onoff_iclzone" in url
        assert "zone_id=1" in url
        assert "on_off_action=off" in url

    async def test_turn_off_noop(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        sut = _make_icl_light()
        sut.data["zoneStatus"] = "off"
        respx_mock.route(dotstar).mock(resp_200)
        await sut.turn_off()
        assert len(respx_mock.calls) == 0

    async def test_set_brightness_percentage_75(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        sut = _make_icl_light()
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_icl_info_response"):
            await sut.set_brightness_percentage(75)
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "set_iclzone_color" in url
        assert "zone_id=1" in url
        assert "dim_level=75" in url
        assert "color_id" not in url

    async def test_set_brightness_percentage_invalid_negative(self) -> None:
        from iaqualink.exception import AqualinkInvalidParameterException

        sut = _make_icl_light()
        with pytest.raises(AqualinkInvalidParameterException):
            await sut.set_brightness_percentage(-1)

    async def test_set_brightness_percentage_invalid_over_100(self) -> None:
        from iaqualink.exception import AqualinkInvalidParameterException

        sut = _make_icl_light()
        with pytest.raises(AqualinkInvalidParameterException):
            await sut.set_brightness_percentage(101)

    async def test_set_brightness_percentage_invalid_non_multiple_of_5(
        self,
    ) -> None:
        from iaqualink.exception import AqualinkInvalidParameterException

        sut = _make_icl_light()
        with pytest.raises(AqualinkInvalidParameterException):
            await sut.set_brightness_percentage(89)

    async def test_set_effect_by_id_4(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        sut = _make_icl_light()
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_icl_info_response"):
            await sut._set_effect_by_id(4)
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "set_iclzone_color" in url
        assert "zone_id=1" in url
        assert "color_id=4" in url
        assert "dim_level=100" in url

    async def test_set_effect_emerald_green(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        sut = _make_icl_light()
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_icl_info_response"):
            await sut.set_effect("Emerald Green")
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "set_iclzone_color" in url
        assert "color_id=6" in url

    async def test_set_effect_off(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        sut = _make_icl_light()
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_icl_info_response"):
            await sut.set_effect("Off")
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "set_iclzone_color" in url
        assert "color_id=0" in url

    async def test_set_effect_invalid_amaranth(self) -> None:
        from iaqualink.exception import AqualinkInvalidParameterException

        sut = _make_icl_light()
        with pytest.raises(AqualinkInvalidParameterException):
            await sut.set_effect("Amaranth")

    async def test_set_rgbw(self, respx_mock: respx.router.MockRouter) -> None:
        sut = _make_icl_light()
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_icl_custom_color_response"):
            await sut.set_rgbw(255, 0, 128)
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "define_iclzone_customcolor" in url
        assert "zone_id=1" in url
        assert "red_val=255" in url
        assert "green_val=0" in url
        assert "blue_val=128" in url
        assert "white_val=0" in url

    async def test_set_rgbw_with_white(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        sut = _make_icl_light()
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_icl_custom_color_response"):
            await sut.set_rgbw(100, 150, 200, white=50)
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "white_val=50" in url

    async def test_set_rgbw_invalid_red(self) -> None:
        from iaqualink.exception import AqualinkInvalidParameterException

        sut = _make_icl_light()
        with pytest.raises(AqualinkInvalidParameterException):
            await sut.set_rgbw(256, 0, 0)

    async def test_set_rgbw_invalid_negative(self) -> None:
        from iaqualink.exception import AqualinkInvalidParameterException

        sut = _make_icl_light()
        with pytest.raises(AqualinkInvalidParameterException):
            await sut.set_rgbw(-1, 0, 0)

    def test_upsert_icl_zones_removes_absent_device(self) -> None:
        sut = _make_icl_light()
        sut.system.devices["icl_zone_1"] = sut
        assert "icl_zone_1" in sut.system.devices
        sut.system._upsert_icl_zones(
            [
                {"zoneId": 1, "zoneStatus": "absent"},
            ]
        )
        assert "icl_zone_1" not in sut.system.devices

    def test_parse_icl_custom_color_response_updates_color_fields(self) -> None:
        import httpx

        sut = _make_icl_light()
        sut.system.devices["icl_zone_1"] = sut
        response = httpx.Response(
            200,
            json={
                "zone_id": "1",
                "red_val": "200",
                "green_val": "100",
                "blue_val": "50",
                "white_val": "25",
            },
        )
        sut.system._parse_icl_custom_color_response(response)
        assert sut.rgbw == (200, 100, 50, 25)
        assert sut._color_id == ICL_CUSTOM_COLOR_ID
        assert sut.effect is None  # color_id=16 excluded from effect


# ---------------------------------------------------------------------------
# IaquaVSPump (VSP)
# ---------------------------------------------------------------------------

_VSP_SPEED_INFO = [
    {"speedid": 1, "speedName": "MED", "speedvalue": 3000, "enabled": "false"},
    {"speedid": 2, "speedName": "HI", "speedvalue": 3450, "enabled": "false"},
    {
        "speedid": 3,
        "speedName": "POLARIS",
        "speedvalue": 3450,
        "enabled": "false",
    },
    {"speedid": 4, "speedName": "LO", "speedvalue": 1800, "enabled": "true"},
    {"speedid": 5, "speedName": "TEMP", "speedvalue": 2000, "enabled": "false"},
    {
        "speedid": 6,
        "speedName": "Temp2",
        "speedvalue": 2250,
        "enabled": "false",
    },
    {
        "speedid": 7,
        "speedName": "Heat Pump",
        "speedvalue": 2750,
        "enabled": "false",
    },
    {
        "speedid": 8,
        "speedName": "In Floor",
        "speedvalue": 2750,
        "enabled": "false",
    },
]


def _make_pump():
    system = make_system()
    data = {
        "name": "vsp_pump_1",
        "state": "0",
        "label": "Main Pump",
        "slot_id": "1",
    }
    return system, IaquaVSPump(system, data)


class TestIaquaVSPump:
    def test_supports_presets_false_before_fetch(self) -> None:
        _, sut = _make_pump()
        assert sut.supports_presets is False

    def test_supports_presets_true_after_fetch_with_presets(self) -> None:
        _, sut = _make_pump()
        sut._speed_presets = _VSP_SPEED_INFO  # type: ignore[assignment]
        assert sut.supports_presets is True

    def test_supports_presets_false_when_speed_presets_empty(self) -> None:
        _, sut = _make_pump()
        sut._speed_presets = []
        assert sut.supports_presets is False

    def test_preset_modes_raises_when_speed_presets_empty(self) -> None:
        _, sut = _make_pump()
        sut._speed_presets = []
        with pytest.raises(AqualinkOperationNotSupportedException):
            _ = sut.preset_modes

    def test_preset_mode_raises_when_speed_presets_empty(self) -> None:
        _, sut = _make_pump()
        sut._speed_presets = []
        with pytest.raises(AqualinkOperationNotSupportedException):
            _ = sut.preset_mode

    def test_preset_modes_raises_before_fetch(self) -> None:
        _, sut = _make_pump()
        with pytest.raises(AqualinkOperationNotSupportedException):
            _ = sut.preset_modes

    def test_preset_mode_raises_before_fetch(self) -> None:
        _, sut = _make_pump()
        with pytest.raises(AqualinkOperationNotSupportedException):
            _ = sut.preset_mode

    def test_preset_modes_after_fetch(self) -> None:
        _, sut = _make_pump()
        sut._speed_presets = _VSP_SPEED_INFO  # type: ignore[assignment]
        assert sut.preset_modes == [
            "MED",
            "HI",
            "POLARIS",
            "LO",
            "TEMP",
            "Temp2",
            "Heat Pump",
            "In Floor",
        ]

    def test_preset_mode_after_fetch(self) -> None:
        _, sut = _make_pump()
        sut._speed_presets = _VSP_SPEED_INFO  # type: ignore[assignment]
        assert sut.preset_mode == "LO"

    def test_preset_mode_none_when_all_disabled(self) -> None:
        _, sut = _make_pump()
        sut._speed_presets = [
            {
                "speedid": 1,
                "speedName": "MED",
                "speedvalue": 3000,
                "enabled": "false",
            },
        ]
        assert sut.preset_mode is None

    async def test_set_preset_mode_raises_before_fetch(self) -> None:
        _, sut = _make_pump()
        with pytest.raises(AqualinkOperationNotSupportedException):
            await sut.set_preset_mode("LO")

    async def test_set_preset_mode_calls_system(self) -> None:
        system, sut = _make_pump()
        sut._speed_presets = _VSP_SPEED_INFO  # type: ignore[assignment]
        with patch.object(system, "set_vsp_speed", return_value={}) as mock_set:
            await sut.set_preset_mode("LO")
        mock_set.assert_awaited_once_with(4, slot_id=1)

    async def test_fetch_speed_populates_presets(self) -> None:
        system, sut = _make_pump()
        vsp_response = {"vsp_speedInfo": _VSP_SPEED_INFO}
        with patch.object(system, "get_vsp_speed", return_value=vsp_response):
            await sut.fetch_speed()
        assert sut._speed_presets == _VSP_SPEED_INFO
        assert sut.preset_mode == "LO"

    async def test_fetch_speed_uses_slot_id_from_data(self) -> None:
        system, sut = _make_pump()
        sut.data["slot_id"] = 5
        vsp_response = {"vsp_speedInfo": _VSP_SPEED_INFO}
        with patch.object(
            system, "get_vsp_speed", return_value=vsp_response
        ) as mock_get:
            await sut.fetch_speed()
        mock_get.assert_awaited_once_with(5)

    def test_apply_speed_update_noop_when_presets_none(self) -> None:
        _, sut = _make_pump()
        sut._speed_presets = None
        sut._apply_speed_update([{"speedId": 1, "status": "Enabled"}])

    def test_apply_speed_update_noop_when_speed_info_empty(self) -> None:
        _, sut = _make_pump()
        sut._speed_presets = _VSP_SPEED_INFO  # type: ignore[assignment]
        original = [dict(p) for p in _VSP_SPEED_INFO]
        sut._apply_speed_update([])
        assert sut._speed_presets == original

    def test_apply_speed_update_sets_enabled(self) -> None:
        _, sut = _make_pump()
        sut._speed_presets = [
            {
                "speedid": 1,
                "speedName": "LO",
                "speedvalue": 1800,
                "enabled": "false",
            },
        ]
        sut._apply_speed_update([{"speedId": 1, "status": "Enabled"}])
        assert sut._speed_presets[0]["enabled"] == "true"

    async def test_set_preset_mode_updates_speed_info(self) -> None:
        system, sut = _make_pump()
        sut._speed_presets = [
            {
                "speedid": 4,
                "speedName": "LO",
                "speedvalue": 1800,
                "enabled": "false",
            },
        ]
        speed_info = [{"speedId": 4, "status": "Enabled", "speedvalue": 1800}]
        with patch.object(
            system,
            "set_vsp_speed",
            return_value={"vsp_speedInfo": speed_info},
        ):
            await sut.set_preset_mode("LO")
        assert sut._speed_presets[0]["enabled"] == "true"

    async def test_set_preset_mode_uses_slot_id_from_data(self) -> None:
        system, sut = _make_pump()
        sut.data["slot_id"] = 5
        sut._speed_presets = _VSP_SPEED_INFO  # type: ignore[assignment]
        with patch.object(system, "set_vsp_speed", return_value={}) as mock_set:
            await sut.set_preset_mode("LO")
        mock_set.assert_awaited_once_with(4, slot_id=5)

    def test_is_on_uses_preset_enabled_when_presets_loaded(self) -> None:
        _, sut = _make_pump()
        all_disabled = [{**p, "enabled": "false"} for p in _VSP_SPEED_INFO]
        sut._speed_presets = all_disabled  # type: ignore[assignment]
        assert sut.is_on is False
        with_one_enabled = [
            {**_VSP_SPEED_INFO[0], "enabled": "true"},
            *_VSP_SPEED_INFO[1:],
        ]
        sut._speed_presets = with_one_enabled  # type: ignore[assignment]
        assert sut.is_on is True

    async def test_turn_on_with_presets_uses_first_preset_speed(self) -> None:
        system, sut = _make_pump()
        all_disabled = [{**p, "enabled": "false"} for p in _VSP_SPEED_INFO]
        sut._speed_presets = all_disabled  # type: ignore[assignment]
        with patch.object(system, "set_vsp_speed", return_value={}) as mock_set:
            await sut.turn_on()
        mock_set.assert_awaited_once_with(1, slot_id=sut.slot_id)


# ---------------------------------------------------------------------------
# IaquaSwcSetPoint / IaquaSwcBoostSwitch (SWC)
# ---------------------------------------------------------------------------


class TestIaquaSwcSetPoint:
    """iAqua SWC set point — pool/spa pairing, wire-protocol URL verification."""

    def test_property_label(self) -> None:
        sut = IaquaSwcSetPoint(make_system(), {**IAQUA_SWC_POOL_SET_POINT_DATA})
        assert sut.label == "Swc Pool Set Point"

    def test_property_current_value(self) -> None:
        sut = IaquaSwcSetPoint(make_system(), {**IAQUA_SWC_POOL_SET_POINT_DATA})
        assert sut.current_value == 50.0

    def test_property_current_value_empty_state(self) -> None:
        sut = IaquaSwcSetPoint(make_system(), {**IAQUA_SWC_POOL_SET_POINT_DATA})
        sut.data["state"] = ""
        assert sut.current_value is None

    def test_property_min_value(self) -> None:
        sut = IaquaSwcSetPoint(make_system(), {**IAQUA_SWC_POOL_SET_POINT_DATA})
        assert sut.min_value == 0.0

    def test_property_max_value(self) -> None:
        sut = IaquaSwcSetPoint(make_system(), {**IAQUA_SWC_POOL_SET_POINT_DATA})
        assert sut.max_value == 100.0

    async def test_set_value_at_min(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        sut = IaquaSwcSetPoint(make_system(), {**IAQUA_SWC_POOL_SET_POINT_DATA})
        respx_mock.route(dotstar).mock(resp_200)
        await sut.set_value(sut.min_value)
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "command=set_swc_config" in url
        assert "poolswcsp=0" in url

    async def test_set_value_at_max(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        sut = IaquaSwcSetPoint(make_system(), {**IAQUA_SWC_POOL_SET_POINT_DATA})
        respx_mock.route(dotstar).mock(resp_200)
        await sut.set_value(sut.max_value)
        assert len(respx_mock.calls) == 1
        url = str(respx_mock.calls[0].request.url)
        assert "command=set_swc_config" in url
        assert "poolswcsp=100" in url

    async def test_set_value_preserves_spa_setpoint(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        system = make_system()
        sut = IaquaSwcSetPoint(system, {**IAQUA_SWC_POOL_SET_POINT_DATA})
        system.devices = {
            "swc_pool_set_point": sut,
            "swc_spa_set_point": IaquaSwcSetPoint(
                system, {"name": "swc_spa_set_point", "state": "35"}
            ),
        }
        respx_mock.route(dotstar).mock(resp_200)
        await sut.set_value(70.0)
        url = str(respx_mock.calls[0].request.url)
        assert "poolswcsp=70" in url
        assert "spaswcsp=35" in url

    async def test_set_value_spa_preserves_pool_setpoint(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        system = make_system()
        sut = IaquaSwcSetPoint(
            system, {"name": "swc_spa_set_point", "state": "35"}
        )
        system.devices = {
            "swc_spa_set_point": sut,
            "swc_pool_set_point": IaquaSwcSetPoint(
                system, {**IAQUA_SWC_POOL_SET_POINT_DATA, "state": "40"}
            ),
        }
        respx_mock.route(dotstar).mock(resp_200)
        await sut.set_value(70.0)
        url = str(respx_mock.calls[0].request.url)
        assert "poolswcsp=40" in url
        assert "spaswcsp=70" in url


class TestIaquaSwcBoostButtons:
    async def test_start_button_sends_default_hrs_and_mode(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        sut = IaquaSwcBoostStartButton(
            make_system(), {"name": "swc_boost_start"}
        )
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_swc_config_response"):
            await sut.press()
        url = str(respx_mock.calls[0].request.url)
        assert "command=control_swc_boost" in url
        assert "boostcontrol=start" in url
        assert "boosthrs=24" in url
        assert "boostmode=pool" in url

    async def test_start_button_uses_last_known_hrs_and_mode(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        system = make_system()
        system.devices["swc_boost_hrs"] = IaquaSensor(
            system, {"name": "swc_boost_hrs", "state": "12"}
        )
        system.devices["swc_boost_mode"] = IaquaSensor(
            system, {"name": "swc_boost_mode", "state": "spillover"}
        )
        sut = IaquaSwcBoostStartButton(system, {"name": "swc_boost_start"})
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_swc_config_response"):
            await sut.press()
        url = str(respx_mock.calls[0].request.url)
        assert "boosthrs=12" in url
        assert "boostmode=spillover" in url

    async def test_stop_button_sends_stop(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        sut = IaquaSwcBoostStopButton(make_system(), {"name": "swc_boost_stop"})
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_swc_config_response"):
            await sut.press()
        url = str(respx_mock.calls[0].request.url)
        assert "command=control_swc_boost" in url
        assert "boostcontrol=stop" in url
        assert "boosthrs" not in url
        assert "boostmode" not in url

    async def test_pause_button_sends_pause(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        sut = IaquaSwcBoostPauseButton(
            make_system(), {"name": "swc_boost_pause"}
        )
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_swc_config_response"):
            await sut.press()
        url = str(respx_mock.calls[0].request.url)
        assert "boostcontrol=pause" in url

    async def test_resume_button_sends_resume(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        sut = IaquaSwcBoostResumeButton(
            make_system(), {"name": "swc_boost_resume"}
        )
        respx_mock.route(dotstar).mock(resp_200)
        with patch.object(sut.system, "_parse_swc_config_response"):
            await sut.press()
        url = str(respx_mock.calls[0].request.url)
        assert "boostcontrol=resume" in url
