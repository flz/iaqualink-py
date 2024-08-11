from __future__ import annotations

import copy
from typing import cast
from asyncio import Future
from unittest.mock import MagicMock, patch

from iaqualink.systems.zs500.device import (
    ZS500_TEMP_CELSIUS_HIGH,
    ZS500_TEMP_CELSIUS_LOW,
    Zs500BinarySensor,
    Zs500Device,
    Zs500Sensor,
    Zs500TemperatureSensor,
    Zs500Switch,
    Zs500Thermostat,
)
from iaqualink.systems.zs500.system import Zs500System

from ...base_test_device import (
    TestBaseBinarySensor,
    TestBaseDevice,
    TestBaseLight,
    TestBaseSensor,
    TestBaseSwitch,
    TestBaseThermostat,
)


class TestZs500Device(TestBaseDevice):
    def setUp(self) -> None:
        super().setUp()

        data = {"serial_number": "SN123456", "device_type": "zs500", "name": "test system"}
        self.system = Zs500System(self.client, data=data)
        self.system._shadow = MagicMock()

        data = {"et": "TEST_DEVICE", "state": 0}
        self.sut = Zs500Device(self.system, data)
        self.sut_class = Zs500Device

    def test_equal(self) -> None:
        assert self.sut == self.sut

    def test_not_equal(self) -> None:
        obj2 = copy.deepcopy(self.sut)
        obj2.data["name"] = "device_2"
        assert self.sut != obj2

    def test_property_name(self) -> None:
        assert self.sut.name == "Test Device"

    def test_property_state(self) -> None:
        assert self.sut.state == self.sut.data["state"]

    def test_not_equal_different_type(self) -> None:
        assert (self.sut == {}) is False

    def test_property_manufacturer(self) -> None:
        assert self.sut.manufacturer == "Zodiac"

    def test_property_model(self) -> None:
        assert self.sut.model == self.sut_class.__name__.replace("Zs500", "")

class TestZs500Sensor(TestZs500Device, TestBaseSensor):
    def setUp(self) -> None:
        super().setUp()

        data = {
            "et": "_SENSOR",
            "state": "connected",
            "type": "air",
            "value": 187
        }
        self.sut = Zs500Device.from_data(self.system, data)
        self.sut_class = Zs500Sensor

    def test_property_name(self) -> None:
        assert self.sut.name == " Sensor"

    def test_property_state(self) -> None:
        assert self.sut.state == self.sut.data["value"]

class TestZs500TemperatureSensor(TestZs500Device, TestBaseSensor):
    def setUp(self) -> None:
        super().setUp()

        data = {
            "et": "AIR_SENSOR",
            "state": "connected",
            "type": "air",
            "value": 187
        }
        self.sut = Zs500Device.from_data(self.system, data)
        self.sut_class = Zs500TemperatureSensor

    def test_property_name(self) -> None:
        assert self.sut.name == "Air Sensor"

    def test_property_state(self) -> None:
        assert self.sut.state == self.sut.data["value"] / 10


class TestZs500BinarySensor(TestZs500Sensor, TestBaseBinarySensor):
    def setUp(self) -> None:
        super().setUp()

        data = {"et": "_BINARY_SENSOR", "state": 0}
        self.sut_class = Zs500BinarySensor
        self.sut = Zs500Device.from_data(self.system, data)

    def test_property_is_on_false(self) -> None:
        self.sut.data["state"] = 0
        super().test_property_is_on_false()
        assert self.sut.is_on is False

    def test_property_is_on_true(self) -> None:
        self.sut.data["state"] = 1
        super().test_property_is_on_true()
        assert self.sut.is_on is True

    def test_property_name(self) -> None:
        assert self.sut.name == " Binary Sensor"

    def test_property_state(self) -> None:
        assert self.sut.state == self.sut.data["state"]


class UpdatesDict(dict):
    def __setitem__(self, name, value):
        value.set_result(True)
        return super().__setitem__(name, value)

class TestZs500Switch(TestZs500BinarySensor, TestBaseSwitch):
    def setUp(self) -> None:
        super().setUp()

        data = {"et": "_SWITCH", "state": 0}
        self.sut = Zs500Device.from_data(self.system, data)
        self.sut_class = Zs500Switch

        self.system._started = True
        self.system.devices["dev0"] = self.sut

    async def test_turn_on(self) -> None:
        self.sut.data["state"] = 0
        with patch.object(self.sut.system._shadow, "publish_update_shadow") as mock:
            future = Future()
            future.set_result(None)
            mock.return_value = future
            self.sut.system._updates = UpdatesDict()
            await self.sut.turn_on()
            mock.assert_called_once()

    async def test_turn_on_noop(self) -> None:
        self.sut.data["state"] = 1
        with patch.object(self.sut.system._shadow, "publish_update_shadow") as mock:
            await self.sut.turn_on()
            mock.assert_not_called()

    async def test_turn_off(self) -> None:
        self.sut.data["state"] = 1
        with patch.object(self.sut.system._shadow, "publish_update_shadow") as mock:
            future = Future()
            future.set_result(None)
            mock.return_value = future
            self.sut.system._updates = UpdatesDict()
            await self.sut.turn_off()
            mock.assert_called_once()

    async def test_turn_off_noop(self) -> None:
        self.sut.data["state"] = 0
        with patch.object(self.sut.system._shadow, "publish_update_shadow") as mock:
            await self.sut.turn_off()
            mock.assert_not_called()

    def test_property_name(self) -> None:
        assert self.sut.name == " Switch"


class TestZs500Thermostat(TestZs500Device, TestBaseThermostat):
    def setUp(self) -> None:
        super().setUp()

        heatpump = Zs500Device.from_data(self.system, {
            "et": "HEAT_PUMP",
            "tsp": 250,
            "sns_0": {
                "type": "water",
                "value": 230
            }
        })
        self.system._started = True
        self.system.devices = { "hp_0": heatpump }

        self.sut = heatpump
        self.sut_class = Zs500Thermostat

    def test_property_label(self) -> None:
        assert self.sut.label == "Heat pump"

    def test_property_name(self) -> None:
        assert self.sut.name == "Heat Pump"

    def test_property_state(self) -> None:
        assert self.sut.state == 23

    def test_property_is_on_true(self) -> None:
        self.sut.data["state"] = 1
        super().test_property_is_on_true()

    def test_property_is_on_false(self) -> None:
        self.sut.data["state"] = 0
        super().test_property_is_on_false()

    def test_property_unit(self) -> None:
        self.sut.system.temp_unit = "F"
        super().test_property_unit()

    def test_property_min_temperature_c(self) -> None:
        self.sut.system.temp_unit = "C"
        super().test_property_min_temperature_f()
        assert self.sut.min_temperature == ZS500_TEMP_CELSIUS_LOW

    def test_property_max_temperature_c(self) -> None:
        self.sut.system.temp_unit = "C"
        super().test_property_max_temperature_c()
        assert self.sut.max_temperature == ZS500_TEMP_CELSIUS_HIGH

    def test_property_current_temperature(self) -> None:
        assert isinstance(self.sut.current_temperature, float)
        assert self.sut.current_temperature == 23

    def test_property_target_temperature(self) -> None:
        assert isinstance(self.sut.target_temperature, float)
        assert self.sut.target_temperature == 25

    async def test_turn_on(self) -> None:
        self.sut.data["state"] = 0
        with patch.object(self.sut.system._shadow, "publish_update_shadow") as mock:
            future = Future()
            future.set_result(None)
            mock.return_value = future
            self.sut.system._updates = UpdatesDict()
            await self.sut.turn_on()
            mock.assert_called_once()

    async def test_turn_on_noop(self) -> None:
        self.sut.data["state"] = 1
        with patch.object(self.sut.system._shadow, "publish_update_shadow") as mock:
            future = Future()
            future.set_result(None)
            mock.return_value = future
            self.sut.system._updates = UpdatesDict()
            await self.sut.turn_on()
            mock.assert_not_called()

    async def test_turn_off(self) -> None:
        self.sut.data["state"] = 1
        with patch.object(self.sut.system._shadow, "publish_update_shadow") as mock:
            future = Future()
            future.set_result(None)
            mock.return_value = future
            self.sut.system._updates = UpdatesDict()
            await self.sut.turn_off()
            mock.assert_called_once()

    async def test_turn_off_noop(self) -> None:
        self.sut.data["state"] = 0
        with patch.object(self.sut.system._shadow, "publish_update_shadow") as mock:
            future = Future()
            future.set_result(None)
            mock.return_value = future
            self.sut.system._updates = UpdatesDict()
            await self.sut.turn_off()
            mock.assert_not_called()

    async def test_set_temperature_86f(self) -> None:
        # Fahrenheit not supported
        pass

    async def test_set_temperature_30c(self) -> None:
        with patch.object(self.sut.system._shadow, "publish_update_shadow") as mock:
            future = Future()
            future.set_result(None)
            mock.return_value = future
            self.sut.system._updates = UpdatesDict()
            await self.sut.set_temperature(30)
            mock.assert_called_once()

            request = mock.call_args.kwargs["request"]
            desired_state = request.state.desired

            temperature = desired_state["equipment"]["hp_0"]["tsp"]
            assert temperature == 300
