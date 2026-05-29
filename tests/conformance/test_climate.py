"""Conformance tests for AqualinkClimate contract."""

from __future__ import annotations

from unittest.mock import PropertyMock, patch

import pytest
import respx
import respx.router

from iaqualink.device import AqualinkClimate
from iaqualink.exception import AqualinkInvalidParameterException

from .conftest import dotstar, resp_200
from .fixtures import ClimateFixture


def test_inheritance(climate_fixture: ClimateFixture) -> None:
    assert isinstance(climate_fixture.device_on, AqualinkClimate)


def test_property_is_on_true(climate_fixture: ClimateFixture) -> None:
    assert climate_fixture.device_on.is_on is True


def test_property_is_on_false(climate_fixture: ClimateFixture) -> None:
    assert climate_fixture.device_off.is_on is False


async def test_turn_on(
    climate_fixture: ClimateFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    await climate_fixture.device_off.turn_on()
    assert len(respx_mock.calls) > 0


async def test_turn_on_noop(
    climate_fixture: ClimateFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not climate_fixture.has_noop_guard:
        respx_mock.route(dotstar).mock(resp_200)
        await climate_fixture.device_on.turn_on()
        assert len(respx_mock.calls) > 0
        return
    respx_mock.route(dotstar).mock(resp_200)
    await climate_fixture.device_on.turn_on()
    assert len(respx_mock.calls) == 0


async def test_turn_off(
    climate_fixture: ClimateFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    await climate_fixture.device_on.turn_off()
    assert len(respx_mock.calls) > 0


async def test_turn_off_noop(
    climate_fixture: ClimateFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not climate_fixture.has_noop_guard:
        respx_mock.route(dotstar).mock(resp_200)
        await climate_fixture.device_off.turn_off()
        assert len(respx_mock.calls) > 0
        return
    respx_mock.route(dotstar).mock(resp_200)
    await climate_fixture.device_off.turn_off()
    assert len(respx_mock.calls) == 0


def test_property_temperature_unit(climate_fixture: ClimateFixture) -> None:
    assert climate_fixture.device_on.temperature_unit in ["C", "F"]


def test_property_min_temp(climate_fixture: ClimateFixture) -> None:
    assert isinstance(climate_fixture.device_on.min_temp, int)


def test_property_max_temp(climate_fixture: ClimateFixture) -> None:
    assert isinstance(climate_fixture.device_on.max_temp, int)


def test_property_min_temp_f(climate_fixture: ClimateFixture) -> None:
    if not climate_fixture.supports_fahrenheit:
        pytest.skip("Device doesn't support Fahrenheit")
    with patch.object(
        type(climate_fixture.device_on),
        "temperature_unit",
        new_callable=PropertyMock,
    ) as mock_unit:
        mock_unit.return_value = "F"
        assert isinstance(climate_fixture.device_on.min_temp, int)


def test_property_min_temp_c(climate_fixture: ClimateFixture) -> None:
    with patch.object(
        type(climate_fixture.device_on),
        "temperature_unit",
        new_callable=PropertyMock,
    ) as mock_unit:
        mock_unit.return_value = "C"
        assert isinstance(climate_fixture.device_on.min_temp, int)


def test_property_max_temp_f(climate_fixture: ClimateFixture) -> None:
    if not climate_fixture.supports_fahrenheit:
        pytest.skip("Device doesn't support Fahrenheit")
    with patch.object(
        type(climate_fixture.device_on),
        "temperature_unit",
        new_callable=PropertyMock,
    ) as mock_unit:
        mock_unit.return_value = "F"
        assert isinstance(climate_fixture.device_on.max_temp, int)


def test_property_max_temp_c(climate_fixture: ClimateFixture) -> None:
    with patch.object(
        type(climate_fixture.device_on),
        "temperature_unit",
        new_callable=PropertyMock,
    ) as mock_unit:
        mock_unit.return_value = "C"
        assert isinstance(climate_fixture.device_on.max_temp, int)


def test_property_current_temperature(
    climate_fixture: ClimateFixture,
) -> None:
    assert isinstance(climate_fixture.device_on.current_temperature, str)


def test_property_target_temperature(
    climate_fixture: ClimateFixture,
) -> None:
    assert isinstance(climate_fixture.device_on.target_temperature, str)


async def test_set_temperature_valid(
    climate_fixture: ClimateFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    min_t = climate_fixture.device_on.min_temp
    max_t = climate_fixture.device_on.max_temp
    valid_temp = (min_t + max_t) // 2
    await climate_fixture.device_on.set_temperature(valid_temp)
    assert len(respx_mock.calls) > 0


async def test_set_temperature_invalid_above_max(
    climate_fixture: ClimateFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    max_t = climate_fixture.device_on.max_temp
    with pytest.raises(AqualinkInvalidParameterException):
        await climate_fixture.device_on.set_temperature(max_t + 100)
    assert len(respx_mock.calls) == 0


async def test_set_temperature_invalid_below_min(
    climate_fixture: ClimateFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    min_t = climate_fixture.device_on.min_temp
    with pytest.raises(AqualinkInvalidParameterException):
        await climate_fixture.device_on.set_temperature(min_t - 100)
    assert len(respx_mock.calls) == 0


def test_from_data(climate_fixture: ClimateFixture) -> None:
    if climate_fixture.expected_class is not None:
        assert isinstance(
            climate_fixture.device_on, climate_fixture.expected_class
        )
