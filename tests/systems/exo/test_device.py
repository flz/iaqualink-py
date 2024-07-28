from __future__ import annotations

import copy
from typing import cast

import pytest

from iaqualink.systems.exo.device import (
    EXO_TEMP_CELSIUS_HIGH,
    EXO_TEMP_CELSIUS_LOW,
    ExoAttributeSensor,
    ExoAttributeSwitch,
    ExoAuxSwitch,
    ExoDevice,
    ExoSensor,
    ExoSwitch,
    ExoThermostat,
)
from iaqualink.systems.exo.system import ExoSystem

from ...base_test_device import (
    TestBaseDevice,
    TestBaseSensor,
    TestBaseSwitch,
    TestBaseThermostat,
)


class TestExoDevice(TestBaseDevice):
    def setUp(self) -> None:
        super().setUp()

        data = {"serial_number": "SN123456", "device_type": "exo"}
        self.system = ExoSystem(self.client, data=data)

        data = {"name": "Test Device", "state": "42"}
        self.sut = ExoDevice(self.system, data)
        self.sut_class = ExoDevice

    def test_equal(self) -> None:
        assert self.sut == self.sut

    def test_not_equal(self) -> None:
        obj2 = copy.deepcopy(self.sut)
        obj2.data["name"] = "Test Device 2"
        assert self.sut != obj2

    def test_property_name(self) -> None:
        assert self.sut.name == self.sut.data["name"]

    def test_property_state(self) -> None:
        assert self.sut.state == str(self.sut.data["state"])

    def test_not_equal_different_type(self) -> None:
        assert (self.sut == {}) is False

    def test_property_manufacturer(self) -> None:
        assert self.sut.manufacturer == "Zodiac"

    def test_property_model(self) -> None:
        assert self.sut.model == self.sut_class.__name__.replace("Exo", "")


class TestExoSensor(TestExoDevice, TestBaseSensor):
    def setUp(self) -> None:
        super().setUp()

        data = {
            "name": "sns_1",
            "sensor_type": "Foo",
            "value": 42,
            "state": 1,
        }
        self.sut = ExoDevice.from_data(self.system, data)
        self.sut_class = ExoSensor

    def test_property_name(self) -> None:
        assert self.sut.name == self.sut.data["sensor_type"].lower().replace(
            " ", "_"
        )

    def test_property_state(self) -> None:
        assert self.sut.state == str(self.sut.data["value"])

    # def test_state_unavailable(self) -> None:
    #    self.sut.data["state"] = 0
    #    assert self.sut.state == ""


class TestExoAttributeSensor(TestExoDevice):
    def setUp(self) -> None:
        super().setUp()

        data = {
            "name": "foo_bar",
            "state": 42,
        }
        self.sut = ExoDevice.from_data(self.system, data)
        self.sut_class = ExoAttributeSensor


class ExoSwitchMixin:
    def test_property_is_on_false(self) -> None:
        self.sut.data["state"] = 0
        super().test_property_is_on_false()
        assert self.sut.is_on is False

    def test_property_is_on_true(self) -> None:
        self.sut.data["state"] = 1
        super().test_property_is_on_true()
        assert self.sut.is_on is True


class TestExoSwitch(TestExoDevice, ExoSwitchMixin, TestBaseSwitch):
    def setUp(self) -> None:
        super().setUp()

        data = {
            "name": "toggle",
            "state": 0,
        }

        # ExoSwitch is an abstract class, not meant to be instantiated directly.
        self.sut = ExoSwitch(self.system, data)
        self.sut_class = ExoSwitch

    async def test_turn_on(self) -> None:
        self.sut.data["state"] = 0
        with pytest.raises(NotImplementedError):
            await super().test_turn_on()

    async def test_turn_on_noop(self) -> None:
        self.sut.data["state"] = 1
        await super().test_turn_on_noop()

    async def test_turn_off(self) -> None:
        self.sut.data["state"] = 1
        with pytest.raises(NotImplementedError):
            await super().test_turn_off()

    async def test_turn_off_noop(self) -> None:
        self.sut.data["state"] = 0
        await super().test_turn_off_noop()


class TestExoAuxSwitch(TestExoDevice, ExoSwitchMixin, TestBaseSwitch):
    def setUp(self) -> None:
        super().setUp()

        data = {
            "name": "aux_1",
            "type": "Foo",
            "mode": "mode",
            "light": 0,
            "state": 1,
        }
        self.sut = ExoDevice.from_data(self.system, data)
        self.sut_class = ExoAuxSwitch

    async def test_turn_on(self) -> None:
        self.sut.data["state"] = 0
        await super().test_turn_on()

    async def test_turn_on_noop(self) -> None:
        self.sut.data["state"] = 1
        await super().test_turn_on_noop()

    async def test_turn_off(self) -> None:
        self.sut.data["state"] = 1
        await super().test_turn_off()

    async def test_turn_off_noop(self) -> None:
        self.sut.data["state"] = 0
        await super().test_turn_off_noop()


class TestExoAttributeSwitch(TestExoDevice, ExoSwitchMixin, TestBaseSwitch):
    def setUp(self) -> None:
        super().setUp()

        data = {
            "name": "boost",
            "state": 1,
        }
        self.sut = ExoDevice.from_data(self.system, data)
        self.sut_class = ExoAttributeSwitch

    async def test_turn_on(self) -> None:
        self.sut.data["state"] = 0
        await super().test_turn_on()

    async def test_turn_on_noop(self) -> None:
        self.sut.data["state"] = 1
        await super().test_turn_on_noop()

    async def test_turn_off(self) -> None:
        self.sut.data["state"] = 1
        await super().test_turn_off()

    async def test_turn_off_noop(self) -> None:
        self.sut.data["state"] = 0
        await super().test_turn_off_noop()


class TestExoThermostat(TestExoDevice, TestBaseThermostat):
    def setUp(self) -> None:
        super().setUp()

        pool_set_point = {
            "name": "heating",
            "enabled": 1,
            "sp": 20,
            "sp_min": 1,
            "sp_max": 40,
        }

        self.pool_set_point = cast(
            ExoThermostat, ExoDevice.from_data(self.system, pool_set_point)
        )

        water_temp = {
            "name": "sns_3",
            "sensor_type": "Water Temp",
            "state": 1,
            "value": 16,
        }
        self.water_temp = ExoDevice.from_data(self.system, water_temp)

        devices = [
            self.pool_set_point,
            self.water_temp,
        ]
        self.system.devices = {x.data["name"]: x for x in devices}

        self.sut = self.pool_set_point
        self.sut_class = ExoThermostat

    def test_property_label(self) -> None:
        assert self.sut.label == "Heating"

    def test_property_name(self) -> None:
        assert self.sut.name == "heating"

    def test_property_state(self) -> None:
        assert self.sut.state == "20"

    def test_property_is_on_true(self) -> None:
        self.sut.data["enabled"] = 1
        super().test_property_is_on_true()

    def test_property_is_on_false(self) -> None:
        self.sut.data["enabled"] = 0
        super().test_property_is_on_false()

    def test_property_unit(self) -> None:
        assert self.sut.unit == "C"

    @pytest.mark.skip
    def test_property_min_temperature_f(self) -> None:
        pass

    def test_property_min_temperature_c(self) -> None:
        self.sut.system.temp_unit = "C"
        super().test_property_min_temperature_c()
        assert self.sut.min_temperature == EXO_TEMP_CELSIUS_LOW

    @pytest.mark.skip
    def test_property_max_temperature_f(self) -> None:
        pass

    def test_property_max_temperature_c(self) -> None:
        self.sut.system.temp_unit = "C"
        super().test_property_max_temperature_c()
        assert self.sut.max_temperature == EXO_TEMP_CELSIUS_HIGH

    def test_property_current_temperature(self) -> None:
        super().test_property_current_temperature()
        assert self.sut.current_temperature == "16"

    def test_property_target_temperature(self) -> None:
        super().test_property_target_temperature()
        assert self.sut.target_temperature == "20"

    async def test_turn_on(self) -> None:
        self.sut.data["enabled"] = 0
        await super().test_turn_on()
        assert len(self.respx_calls) == 1
        content = self.respx_calls[0].request.content.decode("utf-8")
        assert "heating" in content

    async def test_turn_on_noop(self) -> None:
        self.sut.data["enabled"] = 1
        await super().test_turn_on_noop()

    async def test_turn_off(self) -> None:
        self.sut.data["enabled"] = 1
        await super().test_turn_off()
        assert len(self.respx_calls) == 1
        content = self.respx_calls[0].request.content.decode("utf-8")
        assert "heating" in content

    async def test_turn_off_noop(self) -> None:
        self.sut.data["enabled"] = 0
        await super().test_turn_off_noop()

    @pytest.mark.skip
    async def test_set_temperature_86f(self) -> None:
        pass

    async def test_set_temperature_30c(self) -> None:
        await super().test_set_temperature_30c()
        assert len(self.respx_calls) == 1
        content = self.respx_calls[0].request.content.decode("utf-8")
        assert "heating" in content
