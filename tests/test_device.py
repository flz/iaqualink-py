from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkDevice,
    AqualinkLight,
    AqualinkSensor,
    AqualinkSwitch,
    AqualinkThermostat,
)

from .base_test_device import (
    TestBaseBinarySensor,
    TestBaseDevice,
    TestBaseLight,
    TestBaseSensor,
    TestBaseSwitch,
    TestBaseThermostat,
)


class TestAqualinkDevice(TestBaseDevice):
    def setUp(self) -> None:
        system = MagicMock()
        data = {"foo": "bar"}
        self.sut = AqualinkDevice(system, data)

    async def test_repr(self) -> None:
        assert (
            repr(self.sut)
            == f"{self.sut.__class__.__name__}(data={self.sut.data!r})"
        )

    def test_property_name(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_name()

    def test_property_label(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_label()

    def test_property_state(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_state()

    def test_property_manufacturer(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_manufacturer()

    def test_property_model(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_model()


class TestAqualinkSensor(TestBaseSensor, TestAqualinkDevice):
    def setUp(self) -> None:
        system = MagicMock()
        data: dict[str, str] = {}
        self.sut = AqualinkSensor(system, data)


class TestAqualinkBinarySensor(TestBaseBinarySensor, TestAqualinkSensor):
    def setUp(self) -> None:
        system = MagicMock()
        data: dict[str, str] = {}
        self.sut = AqualinkBinarySensor(system, data)

    def test_property_is_on_true(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_is_on_true()

    def test_property_is_on_false(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_is_on_false()


class TestAqualinkSwitch(TestBaseSwitch, TestAqualinkDevice):
    def setUp(self) -> None:
        system = MagicMock()
        data: dict[str, str] = {}
        self.sut = AqualinkSwitch(system, data)

    def test_property_is_on_true(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_is_on_true()

    def test_property_is_on_false(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_is_on_false()

    async def test_turn_on(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_turn_on()

    async def test_turn_on_noop(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_turn_on_noop()

    async def test_turn_off(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_turn_off()

    async def test_turn_off_noop(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_turn_off_noop()


class TestAqualinkLight(TestBaseLight, TestAqualinkDevice):
    def setUp(self) -> None:
        system = MagicMock()
        data: dict[str, str] = {}
        self.sut = AqualinkLight(system, data)

    def test_property_is_on_true(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_is_on_true()

    def test_property_is_on_false(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_is_on_false()

    async def test_turn_off_noop(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_turn_off_noop()

    async def test_turn_off(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_turn_off()

    async def test_turn_on(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_turn_on()

    async def test_turn_on_noop(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_turn_on_noop()

    async def test_set_brightness_75(self) -> None:
        with (
            patch.object(
                type(self.sut),
                "supports_brightness",
                new_callable=PropertyMock(return_value=True),
            ),
            pytest.raises(NotImplementedError),
        ):
            await super().test_set_brightness_75()

    async def test_set_effect_by_name_off(self) -> None:
        with (
            patch.object(
                type(self.sut),
                "supports_effect",
                new_callable=PropertyMock(return_value=True),
            ),
            pytest.raises(NotImplementedError),
        ):
            await super().test_set_effect_by_name_off()

    async def test_set_effect_by_id_4(self) -> None:
        with (
            patch.object(
                type(self.sut),
                "supports_effect",
                new_callable=PropertyMock(return_value=True),
            ),
            pytest.raises(NotImplementedError),
        ):
            await super().test_set_effect_by_id_4()


class TestAqualinkThermostat(TestBaseThermostat, TestAqualinkDevice):
    def setUp(self) -> None:
        system = AsyncMock()
        data: dict[str, str] = {}
        self.sut = AqualinkThermostat(system, data)

    def test_property_is_on_true(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_is_on_true()

    def test_property_is_on_false(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_is_on_false()

    def test_property_unit(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_unit()

    def test_property_min_temperature_f(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_min_temperature_f()

    def test_property_min_temperature_c(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_min_temperature_c()

    def test_property_max_temperature_f(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_max_temperature_f()

    def test_property_max_temperature_c(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_max_temperature_c()

    def test_property_current_temperature(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_current_temperature()

    def test_property_target_temperature(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_target_temperature()

    async def test_turn_on(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_turn_on()

    async def test_turn_on_noop(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_turn_on_noop()

    async def test_turn_off(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_turn_off()

    async def test_turn_off_noop(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_turn_off_noop()

    async def test_set_temperature_86f(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_set_temperature_86f()

    async def test_set_temperature_30c(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_set_temperature_30c()

    async def test_set_temperature_invalid_400f(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_set_temperature_invalid_400f()

    async def test_set_temperature_invalid_204c(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_set_temperature_invalid_204c()
