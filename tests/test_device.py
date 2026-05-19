from __future__ import annotations

import unittest
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
from iaqualink.exception import AqualinkInvalidParameterException

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

    async def _set_temperature(self, _: int) -> None:
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


# ---------------------------------------------------------------------------
# AqualinkNumber.set_value template method — regression suite
# ---------------------------------------------------------------------------


def _make_number_for_template(
    min_val: float,
    max_val: float,
    step: float = 1.0,
) -> AqualinkNumber:
    """Concrete AqualinkNumber for testing set_value template logic directly.

    Skips AqualinkDevice.__init__ — no system/data needed for template tests.
    Records each accepted value in ._calls.
    """
    calls: list[float] = []

    class _N(AqualinkNumber):
        def __init__(self) -> None:
            pass  # skip AqualinkDevice.__init__

        @property
        def label(self) -> str:
            return "N"

        @property
        def name(self) -> str:
            return "n"

        @property
        def manufacturer(self) -> str:
            return ""

        @property
        def model(self) -> str:
            return ""

        @property
        def current_value(self) -> float | None:
            return None

        @property
        def min_value(self) -> float:
            return min_val

        @property
        def max_value(self) -> float:
            return max_val

        @property
        def step(self) -> float:
            return step

        async def _set_value(self, value: float) -> None:
            calls.append(value)

    n = _N()
    n._calls = calls  # type: ignore[attr-defined]
    return n


class TestAqualinkNumberSetValueTemplate(unittest.IsolatedAsyncioTestCase):
    """Regression suite for AqualinkNumber.set_value (template method).

    Tests the validation logic in isolation — no HTTP mocking needed.
    """

    async def test_at_min_valid(self) -> None:
        n = _make_number_for_template(0.0, 100.0, step=25.0)
        await n.set_value(0.0)
        assert n._calls == [0.0]  # type: ignore[attr-defined]

    async def test_at_max_valid(self) -> None:
        n = _make_number_for_template(0.0, 100.0, step=25.0)
        await n.set_value(100.0)
        assert n._calls == [100.0]  # type: ignore[attr-defined]

    async def test_in_range_on_step_valid(self) -> None:
        n = _make_number_for_template(0.0, 3450.0, step=25.0)
        await n.set_value(1500.0)
        assert n._calls == [1500.0]  # type: ignore[attr-defined]

    async def test_below_min_raises(self) -> None:
        n = _make_number_for_template(600.0, 3450.0, step=25.0)
        with pytest.raises(AqualinkInvalidParameterException):
            await n.set_value(575.0)
        assert n._calls == []  # type: ignore[attr-defined]

    async def test_above_max_raises(self) -> None:
        n = _make_number_for_template(600.0, 3450.0, step=25.0)
        with pytest.raises(AqualinkInvalidParameterException):
            await n.set_value(3475.0)
        assert n._calls == []  # type: ignore[attr-defined]

    async def test_not_on_step_raises(self) -> None:
        n = _make_number_for_template(0.0, 3450.0, step=25.0)
        with pytest.raises(AqualinkInvalidParameterException):
            await n.set_value(1501.0)
        assert n._calls == []  # type: ignore[attr-defined]

    async def test_fractional_step_on_step_valid(self) -> None:
        n = _make_number_for_template(0.0, 10.0, step=0.5)
        await n.set_value(1.5)
        assert n._calls == [1.5]  # type: ignore[attr-defined]

    async def test_fractional_step_off_step_raises(self) -> None:
        n = _make_number_for_template(0.0, 10.0, step=0.5)
        with pytest.raises(AqualinkInvalidParameterException):
            await n.set_value(1.3)
        assert n._calls == []  # type: ignore[attr-defined]

    async def test_step_one_any_integer_valid(self) -> None:
        n = _make_number_for_template(0.0, 100.0, step=1.0)
        await n.set_value(37.0)
        assert n._calls == [37.0]  # type: ignore[attr-defined]

    async def test_min_not_at_zero_on_step_valid(self) -> None:
        n = _make_number_for_template(600.0, 3450.0, step=25.0)
        await n.set_value(625.0)
        assert n._calls == [625.0]  # type: ignore[attr-defined]

    async def test_min_not_at_zero_off_step_raises(self) -> None:
        n = _make_number_for_template(600.0, 3450.0, step=25.0)
        with pytest.raises(AqualinkInvalidParameterException):
            await n.set_value(613.0)
        assert n._calls == []  # type: ignore[attr-defined]
