"""Conformance tests for AqualinkNumber contract."""

from __future__ import annotations

import pytest
import respx
import respx.router

from iaqualink.device import AqualinkNumber
from iaqualink.exception import AqualinkInvalidParameterException

from .conftest import dotstar, resp_200
from .fixtures import NumberFixture


def test_inheritance(number_fixture: NumberFixture) -> None:
    assert isinstance(number_fixture.device, AqualinkNumber)


def test_property_current_value(number_fixture: NumberFixture) -> None:
    assert number_fixture.device.current_value is None or isinstance(
        number_fixture.device.current_value, float
    )


def test_property_min_value(number_fixture: NumberFixture) -> None:
    assert isinstance(number_fixture.device.min_value, float)


def test_property_max_value(number_fixture: NumberFixture) -> None:
    assert isinstance(number_fixture.device.max_value, float)


def test_property_min_le_max(number_fixture: NumberFixture) -> None:
    assert number_fixture.device.min_value <= number_fixture.device.max_value


def test_property_step(number_fixture: NumberFixture) -> None:
    assert isinstance(number_fixture.device.step, float)
    assert number_fixture.device.step > 0


def test_property_unit_of_measurement(number_fixture: NumberFixture) -> None:
    assert number_fixture.device.unit_of_measurement is None or isinstance(
        number_fixture.device.unit_of_measurement, str
    )


async def test_set_value_at_min(
    number_fixture: NumberFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    await number_fixture.device.set_value(number_fixture.device.min_value)
    assert len(respx_mock.calls) > 0


async def test_set_value_at_max(
    number_fixture: NumberFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    await number_fixture.device.set_value(number_fixture.device.max_value)
    assert len(respx_mock.calls) > 0


async def test_set_value_below_min(
    number_fixture: NumberFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    with pytest.raises(AqualinkInvalidParameterException):
        await number_fixture.device.set_value(
            number_fixture.device.min_value - 1.0
        )
    assert len(respx_mock.calls) == 0


async def test_set_value_above_max(
    number_fixture: NumberFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    with pytest.raises(AqualinkInvalidParameterException):
        await number_fixture.device.set_value(
            number_fixture.device.max_value + 1.0
        )
    assert len(respx_mock.calls) == 0


def test_from_data(number_fixture: NumberFixture) -> None:
    if number_fixture.expected_class is not None:
        assert isinstance(number_fixture.device, number_fixture.expected_class)


# ---------------------------------------------------------------------------
# Template-method regression tests (no HTTP mocking — pure logic)
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
    n._calls = calls  # type: ignore[attr-defined]  # ty: ignore
    return n


# ---------------------------------------------------------------------------
# Template-method regression tests (no HTTP mocking — pure logic)
# Grouped here to separate from conformance fixture tests above.
# ---------------------------------------------------------------------------


async def test_set_value_template_at_min_valid() -> None:
    n = _make_number_for_template(0.0, 100.0, step=25.0)
    await n.set_value(0.0)
    assert n._calls == [0.0]  # type: ignore[attr-defined]  # ty: ignore


async def test_set_value_template_at_max_valid() -> None:
    n = _make_number_for_template(0.0, 100.0, step=25.0)
    await n.set_value(100.0)
    assert n._calls == [100.0]  # type: ignore[attr-defined]  # ty: ignore


async def test_set_value_template_in_range_on_step_valid() -> None:
    n = _make_number_for_template(0.0, 3450.0, step=25.0)
    await n.set_value(1500.0)
    assert n._calls == [1500.0]  # type: ignore[attr-defined]  # ty: ignore


async def test_set_value_template_below_min_raises() -> None:
    n = _make_number_for_template(600.0, 3450.0, step=25.0)
    with pytest.raises(AqualinkInvalidParameterException):
        await n.set_value(575.0)
    assert n._calls == []  # type: ignore[attr-defined]  # ty: ignore


async def test_set_value_template_above_max_raises() -> None:
    n = _make_number_for_template(600.0, 3450.0, step=25.0)
    with pytest.raises(AqualinkInvalidParameterException):
        await n.set_value(3475.0)
    assert n._calls == []  # type: ignore[attr-defined]  # ty: ignore


async def test_set_value_template_not_on_step_raises() -> None:
    n = _make_number_for_template(0.0, 3450.0, step=25.0)
    with pytest.raises(AqualinkInvalidParameterException):
        await n.set_value(1501.0)
    assert n._calls == []  # type: ignore[attr-defined]  # ty: ignore


async def test_set_value_template_fractional_step_valid() -> None:
    n = _make_number_for_template(0.0, 10.0, step=0.5)
    await n.set_value(1.5)
    assert n._calls == [1.5]  # type: ignore[attr-defined]  # ty: ignore


async def test_set_value_template_fractional_step_off_raises() -> None:
    n = _make_number_for_template(0.0, 10.0, step=0.5)
    with pytest.raises(AqualinkInvalidParameterException):
        await n.set_value(1.3)
    assert n._calls == []  # type: ignore[attr-defined]  # ty: ignore


async def test_set_value_template_step_one_any_integer_valid() -> None:
    n = _make_number_for_template(0.0, 100.0, step=1.0)
    await n.set_value(37.0)
    assert n._calls == [37.0]  # type: ignore[attr-defined]  # ty: ignore


async def test_set_value_template_min_not_at_zero_on_step_valid() -> None:
    n = _make_number_for_template(600.0, 3450.0, step=25.0)
    await n.set_value(625.0)
    assert n._calls == [625.0]  # type: ignore[attr-defined]  # ty: ignore


async def test_set_value_template_min_not_at_zero_off_step_raises() -> None:
    n = _make_number_for_template(600.0, 3450.0, step=25.0)
    with pytest.raises(AqualinkInvalidParameterException):
        await n.set_value(613.0)
    assert n._calls == []  # type: ignore[attr-defined]  # ty: ignore
