"""Conformance tests for AqualinkFan contract."""

from __future__ import annotations

import pytest
import respx
import respx.router

from iaqualink.device import AqualinkFan
from iaqualink.exception import (
    AqualinkInvalidParameterException,
    AqualinkOperationNotSupportedException,
)

from .conftest import dotstar, resp_200
from .fixtures import FanFixture


def test_inheritance(fan_fixture: FanFixture) -> None:
    assert isinstance(fan_fixture.device_on, AqualinkFan)


def test_property_supports_turn_on(fan_fixture: FanFixture) -> None:
    assert isinstance(fan_fixture.device_on.supports_turn_on, bool)


def test_property_supports_turn_off(fan_fixture: FanFixture) -> None:
    assert isinstance(fan_fixture.device_on.supports_turn_off, bool)


def test_property_is_on_true(fan_fixture: FanFixture) -> None:
    if not (
        fan_fixture.device_on.supports_turn_on
        or fan_fixture.device_on.supports_turn_off
    ):
        with pytest.raises(AqualinkOperationNotSupportedException):
            _ = fan_fixture.device_on.is_on
    else:
        assert fan_fixture.device_on.is_on is True


def test_property_is_on_false(fan_fixture: FanFixture) -> None:
    if not (
        fan_fixture.device_off.supports_turn_on
        or fan_fixture.device_off.supports_turn_off
    ):
        pytest.skip("device does not support on/off")
    else:
        assert fan_fixture.device_off.is_on is False


async def test_turn_on(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device_off.supports_turn_on:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await fan_fixture.device_off.turn_on()
        return
    respx_mock.route(dotstar).mock(resp_200)
    await fan_fixture.device_off.turn_on()
    assert len(respx_mock.calls) > 0


async def test_turn_on_noop(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device_on.supports_turn_on:
        pytest.skip("Device doesn't support turn_on")
    respx_mock.route(dotstar).mock(resp_200)
    await fan_fixture.device_on.turn_on()
    assert len(respx_mock.calls) == 0


async def test_turn_off(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device_on.supports_turn_off:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await fan_fixture.device_on.turn_off()
        return
    respx_mock.route(dotstar).mock(resp_200)
    await fan_fixture.device_on.turn_off()
    assert len(respx_mock.calls) > 0


async def test_turn_off_noop(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device_off.supports_turn_off:
        pytest.skip("Device doesn't support turn_off")
    respx_mock.route(dotstar).mock(resp_200)
    await fan_fixture.device_off.turn_off()
    assert len(respx_mock.calls) == 0


def test_property_supports_presets(fan_fixture: FanFixture) -> None:
    assert isinstance(fan_fixture.device_on.supports_presets, bool)


def test_property_preset_modes(fan_fixture: FanFixture) -> None:
    if fan_fixture.device_on.supports_presets:
        assert isinstance(fan_fixture.device_on.preset_modes, list)
        assert len(fan_fixture.device_on.preset_modes) > 0
    else:
        with pytest.raises(AqualinkOperationNotSupportedException):
            _ = fan_fixture.device_on.preset_modes


def test_property_preset_mode(fan_fixture: FanFixture) -> None:
    if fan_fixture.device_on.supports_presets:
        assert fan_fixture.device_on.preset_mode is None or isinstance(
            fan_fixture.device_on.preset_mode, str
        )
    else:
        with pytest.raises(AqualinkOperationNotSupportedException):
            _ = fan_fixture.device_on.preset_mode


def test_property_supports_percentage(fan_fixture: FanFixture) -> None:
    assert isinstance(fan_fixture.device_on.supports_percentage, bool)


def test_property_percentage(fan_fixture: FanFixture) -> None:
    if fan_fixture.device_on.supports_percentage:
        assert fan_fixture.device_on.percentage is None or isinstance(
            fan_fixture.device_on.percentage, float
        )
    else:
        with pytest.raises(AqualinkOperationNotSupportedException):
            _ = fan_fixture.device_on.percentage


async def test_set_percentage_0(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device_on.supports_percentage:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await fan_fixture.device_on.set_percentage(0)
        return
    respx_mock.route(dotstar).mock(resp_200)
    await fan_fixture.device_on.set_percentage(0)
    assert len(respx_mock.calls) > 0


async def test_set_percentage_50(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device_on.supports_percentage:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await fan_fixture.device_on.set_percentage(50)
        return
    respx_mock.route(dotstar).mock(resp_200)
    await fan_fixture.device_on.set_percentage(50)
    assert len(respx_mock.calls) > 0


async def test_set_percentage_100(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device_on.supports_percentage:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await fan_fixture.device_on.set_percentage(100)
        return
    respx_mock.route(dotstar).mock(resp_200)
    await fan_fixture.device_on.set_percentage(100)
    assert len(respx_mock.calls) > 0


async def test_set_percentage_invalid_negative(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device_on.supports_percentage:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await fan_fixture.device_on.set_percentage(-1)
        return
    respx_mock.route(dotstar).mock(resp_200)
    with pytest.raises(AqualinkInvalidParameterException):
        await fan_fixture.device_on.set_percentage(-1)
    assert len(respx_mock.calls) == 0


async def test_set_percentage_invalid_150(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device_on.supports_percentage:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await fan_fixture.device_on.set_percentage(150)
        return
    respx_mock.route(dotstar).mock(resp_200)
    with pytest.raises(AqualinkInvalidParameterException):
        await fan_fixture.device_on.set_percentage(150)
    assert len(respx_mock.calls) == 0


async def test_set_preset_mode(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device_on.supports_presets:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await fan_fixture.device_on.set_preset_mode("any")
        return
    respx_mock.route(dotstar).mock(resp_200)
    preset = fan_fixture.device_on.preset_modes[0]
    await fan_fixture.device_on.set_preset_mode(preset)
    assert len(respx_mock.calls) > 0


async def test_set_preset_mode_invalid(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device_on.supports_presets:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await fan_fixture.device_on.set_preset_mode("nonexistent")
        return
    respx_mock.route(dotstar).mock(resp_200)
    with pytest.raises(AqualinkInvalidParameterException):
        await fan_fixture.device_on.set_preset_mode("nonexistent_preset")
    assert len(respx_mock.calls) == 0


def test_from_data(fan_fixture: FanFixture) -> None:
    if fan_fixture.expected_class is not None:
        assert isinstance(fan_fixture.device_on, fan_fixture.expected_class)
