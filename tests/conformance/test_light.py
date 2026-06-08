"""Conformance tests for AqualinkLight contract."""

from __future__ import annotations

import pytest
import respx
import respx.router

from iaqualink.device import AqualinkLight
from iaqualink.exception import (
    AqualinkInvalidParameterException,
    AqualinkOperationNotSupportedException,
)

from .conftest import dotstar, resp_200
from .fixtures import LightFixture


def test_inheritance(light_fixture: LightFixture) -> None:
    assert isinstance(light_fixture.device_on, AqualinkLight)


def test_property_is_on_true(light_fixture: LightFixture) -> None:
    assert light_fixture.device_on.is_on is True


def test_property_is_on_false(light_fixture: LightFixture) -> None:
    assert light_fixture.device_off.is_on is False


async def test_turn_on(
    light_fixture: LightFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    await light_fixture.device_off.turn_on()
    assert len(respx_mock.calls) > 0


async def test_turn_on_noop(
    light_fixture: LightFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    await light_fixture.device_on.turn_on()
    if light_fixture.has_noop_guard:
        assert len(respx_mock.calls) == 0
    else:
        assert len(respx_mock.calls) > 0


async def test_turn_off(
    light_fixture: LightFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    await light_fixture.device_on.turn_off()
    assert len(respx_mock.calls) > 0


async def test_turn_off_noop(
    light_fixture: LightFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    await light_fixture.device_off.turn_off()
    if light_fixture.has_noop_guard:
        assert len(respx_mock.calls) == 0
    else:
        assert len(respx_mock.calls) > 0


def test_property_supports_brightness(light_fixture: LightFixture) -> None:
    assert isinstance(light_fixture.device_on.supports_brightness, bool)


def test_property_supports_effect(light_fixture: LightFixture) -> None:
    assert isinstance(light_fixture.device_on.supports_effect, bool)


def test_property_brightness_percentage(light_fixture: LightFixture) -> None:
    if not light_fixture.device_on.supports_brightness:
        pytest.skip("Device doesn't support brightness")
    assert isinstance(light_fixture.device_on.brightness_percentage, int)
    assert 0 <= light_fixture.device_on.brightness_percentage <= 100


def test_property_effect(light_fixture: LightFixture) -> None:
    if not light_fixture.device_on.supports_effect:
        pytest.skip("Device doesn't support effects")
    assert isinstance(light_fixture.device_on.effect, str)


def test_property_effect_list(light_fixture: LightFixture) -> None:
    if not light_fixture.device_on.supports_effect:
        pytest.skip("Device doesn't support effects")
    assert isinstance(light_fixture.device_on.effect_list, list)


async def test_set_brightness_percentage_75(
    light_fixture: LightFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not light_fixture.device_on.supports_brightness:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await light_fixture.device_on.set_brightness_percentage(75)
        return

    respx_mock.route(dotstar).mock(resp_200)
    await light_fixture.device_on.set_brightness_percentage(75)
    assert len(respx_mock.calls) > 0


async def test_set_brightness_percentage_invalid_89(
    light_fixture: LightFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not light_fixture.device_on.supports_brightness:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await light_fixture.device_on.set_brightness_percentage(89)
        return

    if not light_fixture.has_brightness_step_validation:
        pytest.skip(
            "Device accepts any 0–100% value; step validation not enforced"
        )

    respx_mock.route(dotstar).mock(resp_200)
    with pytest.raises(AqualinkInvalidParameterException):
        await light_fixture.device_on.set_brightness_percentage(89)
    assert len(respx_mock.calls) == 0


async def test_set_effect_off(
    light_fixture: LightFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not light_fixture.device_on.supports_effect:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await light_fixture.device_on.set_effect("Off")
        return

    respx_mock.route(dotstar).mock(resp_200)
    await light_fixture.device_on.set_effect("Off")
    assert len(respx_mock.calls) > 0


async def test_set_effect_invalid_amaranth(
    light_fixture: LightFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not light_fixture.device_on.supports_effect:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await light_fixture.device_on.set_effect("Amaranth")
        return

    respx_mock.route(dotstar).mock(resp_200)
    with pytest.raises(AqualinkInvalidParameterException):
        await light_fixture.device_on.set_effect("Amaranth")
    assert len(respx_mock.calls) == 0


def test_from_data(light_fixture: LightFixture) -> None:
    if light_fixture.expected_class is not None:
        assert isinstance(light_fixture.device_on, light_fixture.expected_class)
