from __future__ import annotations

import copy
import json
from typing import cast

import pytest
import respx
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

from ...conftest import TestBase, dotstar, resp_200
from .factories import (
    EXO_ATTRIBUTE_SENSOR_DATA,
    EXO_DEVICE_DATA,
    EXO_FILTER_PUMP_ON_DATA,
    EXO_HEATING_ON_DATA,
    EXO_SENSOR_DATA,
    EXO_WATER_TEMP_DATA,
    make_system,
)


class TestExoDevice(TestBase):
    """EXO-specific device tests — routing, equality, state parsing."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.sut = ExoDevice(self.system, {**EXO_DEVICE_DATA})

    def test_equal(self) -> None:
        assert self.sut == self.sut

    def test_not_equal(self) -> None:
        obj2 = copy.deepcopy(self.sut)
        obj2.data["name"] = "Test Device 2"
        assert self.sut != obj2

    def test_not_equal_different_type(self) -> None:
        assert (self.sut == {}) is False

    def test_property_name(self) -> None:
        assert self.sut.name == self.sut.data["name"]

    def test_property_state(self) -> None:
        assert self.sut.state == str(self.sut.data["state"])

    def test_property_manufacturer(self) -> None:
        assert self.sut.manufacturer == "Zodiac"

    def test_property_model(self) -> None:
        assert self.sut.model == "Device"


class TestExoSensor(TestBase):
    """EXO-specific sensor tests — name/value derivation from data."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.sut = ExoDevice.from_data(self.system, {**EXO_SENSOR_DATA})

    def test_from_data(self) -> None:
        assert isinstance(self.sut, ExoSensor)

    def test_property_name(self) -> None:
        assert self.sut.name == self.sut.data["sensor_type"].lower().replace(
            " ", "_"
        )

    def test_property_value(self) -> None:
        assert self.sut.value == str(self.sut.data["value"])


class TestExoAttributeSensor(TestBase):
    """EXO attribute sensor — value from state field."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.sut = ExoDevice.from_data(
            self.system, {**EXO_ATTRIBUTE_SENSOR_DATA}
        )

    def test_from_data(self) -> None:
        assert isinstance(self.sut, ExoAttributeSensor)

    def test_property_value(self) -> None:
        assert self.sut.value == str(self.sut.data["state"])


class TestExoErrorSensor(TestBase):
    """EXO error sensor — routing and label."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.sut = ExoDevice.from_data(
            self.system, {"name": "error_code", "state": 0}
        )

    def test_from_data(self) -> None:
        assert isinstance(self.sut, ExoErrorSensor)

    def test_property_label(self) -> None:
        assert self.sut.label == "Error Code"

    def test_property_value(self) -> None:
        assert self.sut.value == "0"

    def test_error_state_routing(self) -> None:
        data = {"name": "error_state", "state": 0}
        device = ExoDevice.from_data(self.system, data)
        assert isinstance(device, ExoErrorSensor)
        assert device.label == "Error State"


class TestExoSwitch(TestBase):
    """ExoSwitch is abstract — turn_on/off raises NotImplementedError."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.sut = ExoSwitch(self.system, {"name": "toggle", "state": 0})

    def test_is_on_from_state(self) -> None:
        self.sut.data["state"] = 1
        assert self.sut.is_on is True
        self.sut.data["state"] = 0
        assert self.sut.is_on is False

    async def test_turn_on_raises(self) -> None:
        self.sut.data["state"] = 0
        with pytest.raises(NotImplementedError):
            await self.sut.turn_on()

    async def test_turn_off_raises(self) -> None:
        self.sut.data["state"] = 1
        with pytest.raises(NotImplementedError):
            await self.sut.turn_off()


class TestExoFilterPump(TestBase):
    """ExoFilterPump wire-protocol tests — verifies JSON payloads."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.sut = ExoDevice.from_data(self.system, {**EXO_FILTER_PUMP_ON_DATA})

    def test_from_data(self) -> None:
        assert isinstance(self.sut, ExoFilterPump)

    @respx.mock
    async def test_turn_on_payload(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        self.sut.data["state"] = 0
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.turn_on()
        assert len(respx_mock.calls) == 1
        payload = json.loads(respx_mock.calls[0].request.content)
        assert payload == {
            "state": {
                "desired": {
                    "equipment": {"swc_0": {"filter_pump": {"state": 1}}}
                }
            }
        }

    @respx.mock
    async def test_turn_off_payload(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        self.sut.data["state"] = 1
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.turn_off()
        assert len(respx_mock.calls) == 1
        payload = json.loads(respx_mock.calls[0].request.content)
        assert payload == {
            "state": {
                "desired": {
                    "equipment": {"swc_0": {"filter_pump": {"state": 0}}}
                }
            }
        }


class TestExoHeater(TestBase):
    """ExoHeater — from_data routing and label."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()
        self.sut = ExoDevice.from_data(
            self.system, {"name": "heater", "state": 1}
        )

    def test_from_data(self) -> None:
        assert type(self.sut) is ExoHeater

    def test_property_label(self) -> None:
        assert self.sut.label == "Heater"

    def test_property_state(self) -> None:
        assert self.sut.state == "1"


class TestExoClimate(TestBase):
    """ExoClimate — temperature bounds, wire-protocol for heating commands."""

    def setUp(self) -> None:
        super().setUp()

        self.system = make_system()

        self.pool_set_point = cast(
            ExoClimate,
            ExoDevice.from_data(self.system, {**EXO_HEATING_ON_DATA}),
        )

        self.water_temp = ExoDevice.from_data(
            self.system, {**EXO_WATER_TEMP_DATA}
        )

        devices = [self.pool_set_point, self.water_temp]
        self.system.devices = {x.data["name"]: x for x in devices}

        self.sut = self.pool_set_point

    def test_from_data(self) -> None:
        assert isinstance(self.sut, ExoClimate)

    def test_property_label(self) -> None:
        assert self.sut.label == "Heating"

    def test_property_state(self) -> None:
        assert self.sut.state == "20"

    def test_property_temperature_unit(self) -> None:
        assert self.sut.temperature_unit == "C"

    def test_property_min_temp(self) -> None:
        assert self.sut.min_temp == EXO_TEMP_CELSIUS_LOW

    def test_property_max_temp(self) -> None:
        assert self.sut.max_temp == EXO_TEMP_CELSIUS_HIGH

    def test_property_current_temperature(self) -> None:
        assert self.sut.current_temperature == "16"

    def test_property_target_temperature(self) -> None:
        assert self.sut.target_temperature == "20"

    @respx.mock
    async def test_turn_on_payload(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        self.sut.data["enabled"] = 0
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.turn_on()
        assert len(respx_mock.calls) == 1
        content = respx_mock.calls[0].request.content.decode("utf-8")
        assert "heating" in content

    @respx.mock
    async def test_turn_off_payload(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        self.sut.data["enabled"] = 1
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.turn_off()
        assert len(respx_mock.calls) == 1
        content = respx_mock.calls[0].request.content.decode("utf-8")
        assert "heating" in content

    @respx.mock
    async def test_set_temperature_payload(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.set_temperature(30)
        assert len(respx_mock.calls) == 1
        content = respx_mock.calls[0].request.content.decode("utf-8")
        assert "heating" in content

    async def test_set_temperature_too_low(self) -> None:
        with pytest.raises(AqualinkInvalidParameterException):
            await self.sut.set_temperature(0)

    async def test_set_temperature_too_high(self) -> None:
        with pytest.raises(AqualinkInvalidParameterException):
            await self.sut.set_temperature(41)
