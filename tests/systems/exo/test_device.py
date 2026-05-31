from __future__ import annotations

import json
from typing import Any, cast

import pytest
import respx.router

from iaqualink.exception import AqualinkInvalidParameterException
from iaqualink.systems.exo.device import (
    EXO_TEMP_CELSIUS_HIGH,
    EXO_TEMP_CELSIUS_LOW,
    ExoAttributeSensor,
    ExoClimate,
    ExoDevice,
    ExoErrorSensor,
    ExoFilterPump,
    ExoHeater,
    ExoSensor,
    ExoSwitch,
)

from ...conftest import dotstar, resp_200
from .factories import (
    EXO_ATTRIBUTE_SENSOR_DATA,
    EXO_DEVICE_DATA,
    EXO_FILTER_PUMP_ON_DATA,
    EXO_HEATING_ON_DATA,
    EXO_SENSOR_DATA,
    EXO_WATER_TEMP_DATA,
    make_system,
)


class TestExoDevice:
    """EXO base device — name/state derivation from data fields."""

    def test_property_name(self) -> None:
        sut = ExoDevice(make_system(), {**EXO_DEVICE_DATA})
        assert sut.name == sut.data["name"]

    def test_property_state(self) -> None:
        sut = ExoDevice(make_system(), {**EXO_DEVICE_DATA})
        assert sut.state == str(sut.data["state"])

    def test_property_manufacturer(self) -> None:
        sut = ExoDevice(make_system(), {**EXO_DEVICE_DATA})
        assert sut.manufacturer == "Zodiac"

    def test_property_model(self) -> None:
        sut = ExoDevice(make_system(), {**EXO_DEVICE_DATA})
        assert sut.model == "Device"


class TestExoSensor:
    """EXO sensor — name/value derivation from data."""

    def test_from_data(self) -> None:
        sut = ExoDevice.from_data(make_system(), {**EXO_SENSOR_DATA})
        assert isinstance(sut, ExoSensor)

    def test_property_name(self) -> None:
        sut = ExoDevice.from_data(make_system(), {**EXO_SENSOR_DATA})
        assert sut.name == sut.data["sensor_type"].lower().replace(" ", "_")

    def test_property_value(self) -> None:
        sut = cast(
            ExoSensor, ExoDevice.from_data(make_system(), {**EXO_SENSOR_DATA})
        )
        assert sut.value == str(sut.data["value"])


class TestExoAttributeSensor:
    """EXO attribute sensor — value from state field."""

    def test_from_data(self) -> None:
        sut = ExoDevice.from_data(make_system(), {**EXO_ATTRIBUTE_SENSOR_DATA})
        assert isinstance(sut, ExoAttributeSensor)

    def test_property_value(self) -> None:
        sut = cast(
            ExoAttributeSensor,
            ExoDevice.from_data(make_system(), {**EXO_ATTRIBUTE_SENSOR_DATA}),
        )
        assert sut.value == str(sut.data["state"])


_ERROR_CODE_DATA: dict[str, Any] = {"name": "error_code", "state": 0}
_ERROR_STATE_DATA: dict[str, Any] = {"name": "error_state", "state": 0}


class TestExoErrorSensor:
    """EXO error sensor — routing and label."""

    def test_from_data(self) -> None:
        sut = ExoDevice.from_data(make_system(), _ERROR_CODE_DATA)
        assert isinstance(sut, ExoErrorSensor)

    def test_property_label(self) -> None:
        sut = cast(
            ExoErrorSensor, ExoDevice.from_data(make_system(), _ERROR_CODE_DATA)
        )
        assert sut.label == "Error Code"

    def test_property_value(self) -> None:
        sut = cast(
            ExoErrorSensor, ExoDevice.from_data(make_system(), _ERROR_CODE_DATA)
        )
        assert sut.value == "0"

    def test_error_state_routing(self) -> None:
        sut = ExoDevice.from_data(make_system(), _ERROR_STATE_DATA)
        assert isinstance(sut, ExoErrorSensor)
        assert sut.label == "Error State"


_SWITCH_ON_DATA: dict[str, Any] = {"name": "toggle", "state": 1}
_SWITCH_OFF_DATA: dict[str, Any] = {"name": "toggle", "state": 0}


class TestExoSwitch:
    """ExoSwitch is abstract — turn_on/off raises NotImplementedError."""

    def test_is_on_true(self) -> None:
        sut = ExoSwitch(make_system(), _SWITCH_ON_DATA)
        assert sut.is_on is True

    def test_is_on_false(self) -> None:
        sut = ExoSwitch(make_system(), _SWITCH_OFF_DATA)
        assert sut.is_on is False

    async def test_turn_on_raises(self) -> None:
        sut = ExoSwitch(make_system(), _SWITCH_OFF_DATA)
        with pytest.raises(NotImplementedError):
            await sut.turn_on()

    async def test_turn_off_raises(self) -> None:
        sut = ExoSwitch(make_system(), _SWITCH_ON_DATA)
        with pytest.raises(NotImplementedError):
            await sut.turn_off()


class TestExoFilterPump:
    """ExoFilterPump wire-protocol tests — verifies JSON payloads."""

    def test_from_data(self) -> None:
        sut = ExoDevice.from_data(make_system(), {**EXO_FILTER_PUMP_ON_DATA})
        assert isinstance(sut, ExoFilterPump)

    async def test_turn_on_payload(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        pump_off: dict[str, Any] = {**EXO_FILTER_PUMP_ON_DATA, "state": 0}
        sut = cast(ExoFilterPump, ExoDevice.from_data(make_system(), pump_off))
        respx_mock.route(dotstar).mock(resp_200)
        await sut.turn_on()
        assert len(respx_mock.calls) == 1
        payload = json.loads(respx_mock.calls[0].request.content)
        assert payload == {
            "state": {
                "desired": {
                    "equipment": {"swc_0": {"filter_pump": {"state": 1}}}
                }
            }
        }

    async def test_turn_off_payload(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        pump_on: dict[str, Any] = {**EXO_FILTER_PUMP_ON_DATA, "state": 1}
        sut = cast(ExoFilterPump, ExoDevice.from_data(make_system(), pump_on))
        respx_mock.route(dotstar).mock(resp_200)
        await sut.turn_off()
        assert len(respx_mock.calls) == 1
        payload = json.loads(respx_mock.calls[0].request.content)
        assert payload == {
            "state": {
                "desired": {
                    "equipment": {"swc_0": {"filter_pump": {"state": 0}}}
                }
            }
        }


_HEATER_DATA: dict[str, Any] = {"name": "heater", "state": 1}


class TestExoHeater:
    """ExoHeater — from_data routing and label."""

    def test_from_data(self) -> None:
        sut = ExoDevice.from_data(make_system(), _HEATER_DATA)
        assert type(sut) is ExoHeater

    def test_property_label(self) -> None:
        sut = ExoDevice.from_data(make_system(), _HEATER_DATA)
        assert sut.label == "Heater"

    def test_property_state(self) -> None:
        sut = ExoDevice.from_data(make_system(), _HEATER_DATA)
        assert sut.state == "1"


def _make_exo_climate():
    """Return (system, sut) for ExoClimate tests."""
    system = make_system()
    pool_set_point = cast(
        ExoClimate,
        ExoDevice.from_data(system, {**EXO_HEATING_ON_DATA}),
    )
    water_temp = ExoDevice.from_data(system, {**EXO_WATER_TEMP_DATA})
    system.devices = {x.data["name"]: x for x in [pool_set_point, water_temp]}
    return system, pool_set_point


class TestExoClimate:
    """ExoClimate — temperature bounds, wire-protocol for heating commands."""

    def test_from_data(self) -> None:
        _, sut = _make_exo_climate()
        assert isinstance(sut, ExoClimate)

    def test_property_label(self) -> None:
        _, sut = _make_exo_climate()
        assert sut.label == "Heating"

    def test_property_state(self) -> None:
        _, sut = _make_exo_climate()
        assert sut.state == "20"

    def test_property_temperature_unit(self) -> None:
        _, sut = _make_exo_climate()
        assert sut.temperature_unit == "C"

    def test_property_min_temp(self) -> None:
        _, sut = _make_exo_climate()
        assert sut.min_temp == EXO_TEMP_CELSIUS_LOW

    def test_property_max_temp(self) -> None:
        _, sut = _make_exo_climate()
        assert sut.max_temp == EXO_TEMP_CELSIUS_HIGH

    def test_property_current_temperature(self) -> None:
        _, sut = _make_exo_climate()
        assert sut.current_temperature == "16"

    def test_property_target_temperature(self) -> None:
        _, sut = _make_exo_climate()
        assert sut.target_temperature == "20"

    async def test_turn_on_payload(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        _, sut = _make_exo_climate()
        sut.data["enabled"] = 0
        respx_mock.route(dotstar).mock(resp_200)
        await sut.turn_on()
        assert len(respx_mock.calls) == 1
        content = respx_mock.calls[0].request.content.decode("utf-8")
        assert "heating" in content

    async def test_turn_off_payload(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        _, sut = _make_exo_climate()
        sut.data["enabled"] = 1
        respx_mock.route(dotstar).mock(resp_200)
        await sut.turn_off()
        assert len(respx_mock.calls) == 1
        content = respx_mock.calls[0].request.content.decode("utf-8")
        assert "heating" in content

    async def test_set_temperature_payload(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        _, sut = _make_exo_climate()
        respx_mock.route(dotstar).mock(resp_200)
        await sut.set_temperature(30)
        assert len(respx_mock.calls) == 1
        content = respx_mock.calls[0].request.content.decode("utf-8")
        assert "heating" in content

    async def test_set_temperature_too_low(self) -> None:
        _, sut = _make_exo_climate()
        with pytest.raises(AqualinkInvalidParameterException):
            await sut.set_temperature(0)

    async def test_set_temperature_too_high(self) -> None:
        _, sut = _make_exo_climate()
        with pytest.raises(AqualinkInvalidParameterException):
            await sut.set_temperature(41)
