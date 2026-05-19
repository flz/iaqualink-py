from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest

from iaqualink.device import (
    AqualinkBinarySensor,
    AqualinkClimate,
    AqualinkDevice,
    AqualinkFan,
    AqualinkLight,
    AqualinkNumber,
    AqualinkSensor,
    AqualinkSwitch,
)

from .base_test_device import (
    TestBaseBinarySensor,
    TestBaseClimate,
    TestBaseDevice,
    TestBaseFan,
    TestBaseLight,
    TestBaseNumber,
    TestBaseSensor,
    TestBaseSwitch,
)

# Minimal concrete stubs that satisfy ABC but raise NotImplementedError for
# every abstract member, letting the base-class tests check that behaviour.


class _ConcreteDevice(AqualinkDevice):
    @property
    def label(self) -> str:
        raise NotImplementedError

    @property
    def name(self) -> str:
        raise NotImplementedError

    @property
    def manufacturer(self) -> str:
        raise NotImplementedError

    @property
    def model(self) -> str:
        raise NotImplementedError


class _ConcreteSensor(_ConcreteDevice, AqualinkSensor):
    @property
    def value(self) -> str:
        raise NotImplementedError


class _ConcreteBinarySensor(_ConcreteDevice, AqualinkBinarySensor):
    @property
    def is_on(self) -> bool:
        raise NotImplementedError


class _ConcreteSwitch(_ConcreteDevice, AqualinkSwitch):
    @property
    def is_on(self) -> bool:
        raise NotImplementedError

    async def turn_on(self) -> None:
        raise NotImplementedError

    async def turn_off(self) -> None:
        raise NotImplementedError


class _ConcreteLight(_ConcreteDevice, AqualinkLight):
    @property
    def is_on(self) -> bool:
        raise NotImplementedError

    async def turn_on(self) -> None:
        raise NotImplementedError

    async def turn_off(self) -> None:
        raise NotImplementedError


class _ConcreteClimate(_ConcreteDevice, AqualinkClimate):
    @property
    def is_on(self) -> bool:
        raise NotImplementedError

    async def turn_on(self) -> None:
        raise NotImplementedError

    async def turn_off(self) -> None:
        raise NotImplementedError

    @property
    def temperature_unit(self) -> str:
        raise NotImplementedError

    @property
    def current_temperature(self) -> str:
        raise NotImplementedError

    @property
    def target_temperature(self) -> str:
        raise NotImplementedError

    @property
    def max_temp(self) -> int:
        raise NotImplementedError

    @property
    def min_temp(self) -> int:
        raise NotImplementedError

    async def set_temperature(self, _: int) -> None:
        raise NotImplementedError


class _ConcreteNumber(_ConcreteDevice, AqualinkNumber):
    @property
    def current_value(self) -> float | None:
        raise NotImplementedError

    @property
    def min_value(self) -> float:
        raise NotImplementedError

    @property
    def max_value(self) -> float:
        raise NotImplementedError

    async def _set_value(self, value: float) -> None:
        raise NotImplementedError


class TestAqualinkDevice(TestBaseDevice):
    def setUp(self) -> None:
        self.sut = _ConcreteDevice(MagicMock(), {"foo": "bar"})

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

    def test_property_manufacturer(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_manufacturer()

    def test_property_model(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_model()


class TestAqualinkSensor(TestBaseSensor, TestAqualinkDevice):
    def setUp(self) -> None:
        self.sut = _ConcreteSensor(MagicMock(), {})

    def test_property_value(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_value()


class TestAqualinkBinarySensor(TestBaseBinarySensor, TestAqualinkDevice):
    def setUp(self) -> None:
        self.sut = _ConcreteBinarySensor(MagicMock(), {})

    def test_property_is_on_true(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_is_on_true()

    def test_property_is_on_false(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_is_on_false()


class TestAqualinkSwitch(TestBaseSwitch, TestAqualinkDevice):
    def setUp(self) -> None:
        self.sut = _ConcreteSwitch(MagicMock(), {})

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
        self.sut = _ConcreteLight(MagicMock(), {})

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

    async def test_set_brightness_percentage_75(self) -> None:
        with (
            patch.object(
                type(self.sut),
                "supports_brightness",
                new_callable=PropertyMock(return_value=True),
            ),
            pytest.raises(NotImplementedError),
        ):
            await super().test_set_brightness_percentage_75()

    async def test_set_effect_off(self) -> None:
        with (
            patch.object(
                type(self.sut),
                "supports_effect",
                new_callable=PropertyMock(return_value=True),
            ),
            pytest.raises(NotImplementedError),
        ):
            await super().test_set_effect_off()


class TestAqualinkClimate(TestBaseClimate, TestAqualinkDevice):
    def setUp(self) -> None:
        self.sut = _ConcreteClimate(AsyncMock(), {})

    def test_property_is_on_true(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_is_on_true()

    def test_property_is_on_false(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_is_on_false()

    def test_property_temperature_unit(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_temperature_unit()

    def test_property_min_temp_f(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_min_temp_f()

    def test_property_min_temp_c(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_min_temp_c()

    def test_property_max_temp_f(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_max_temp_f()

    def test_property_max_temp_c(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_max_temp_c()

    def test_property_current_temperature(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_current_temperature()

    def test_property_target_temperature(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_target_temperature()

    async def test_turn_on(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_turn_on()

    async def test_turn_off(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_turn_off()

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


class TestAqualinkNumber(TestBaseNumber, TestAqualinkDevice):
    def setUp(self) -> None:
        self.sut = _ConcreteNumber(MagicMock(), {})

    def test_property_current_value(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_current_value()

    def test_property_min_value(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_min_value()

    def test_property_max_value(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_max_value()

    def test_property_min_le_max(self) -> None:
        with pytest.raises(NotImplementedError):
            super().test_property_min_le_max()

    async def test_set_value_at_min(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_set_value_at_min()

    async def test_set_value_at_max(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_set_value_at_max()

    async def test_set_value_below_min(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_set_value_below_min()

    async def test_set_value_above_max(self) -> None:
        with pytest.raises(NotImplementedError):
            await super().test_set_value_above_max()


class _ConcreteFan(_ConcreteDevice, AqualinkFan):
    pass


class TestAqualinkFan(TestBaseFan, TestAqualinkDevice):
    def setUp(self) -> None:
        self.sut = _ConcreteFan(MagicMock(), {})
