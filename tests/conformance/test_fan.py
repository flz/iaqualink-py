"""Conformance tests for AqualinkFan contract."""

from __future__ import annotations

from unittest.mock import PropertyMock, patch

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
    assert isinstance(fan_fixture.device, AqualinkFan)


def test_property_supports_turn_on(fan_fixture: FanFixture) -> None:
    assert isinstance(fan_fixture.device.supports_turn_on, bool)


def test_property_supports_turn_off(fan_fixture: FanFixture) -> None:
    assert isinstance(fan_fixture.device.supports_turn_off, bool)


def test_property_is_on(fan_fixture: FanFixture) -> None:
    if not (
        fan_fixture.device.supports_turn_on
        or fan_fixture.device.supports_turn_off
    ):
        with pytest.raises(AqualinkOperationNotSupportedException):
            _ = fan_fixture.device.is_on
    else:
        assert isinstance(fan_fixture.device.is_on, bool)


async def test_turn_on(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device.supports_turn_on:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await fan_fixture.device.turn_on()
        return
    respx_mock.route(dotstar).mock(resp_200)
    with patch.object(
        type(fan_fixture.device),
        "is_on",
        new_callable=PropertyMock(return_value=False),
    ):
        await fan_fixture.device.turn_on()
        assert len(respx_mock.calls) > 0


async def test_turn_on_noop(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device.supports_turn_on:
        pytest.skip("Device doesn't support turn_on")
    with patch.object(
        type(fan_fixture.device),
        "is_on",
        new_callable=PropertyMock(return_value=True),
    ):
        respx_mock.route(dotstar).mock(resp_200)
        await fan_fixture.device.turn_on()
        assert len(respx_mock.calls) == 0


async def test_turn_off(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device.supports_turn_off:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await fan_fixture.device.turn_off()
        return
    respx_mock.route(dotstar).mock(resp_200)
    with patch.object(
        type(fan_fixture.device),
        "is_on",
        new_callable=PropertyMock(return_value=True),
    ):
        await fan_fixture.device.turn_off()
        assert len(respx_mock.calls) > 0


async def test_turn_off_noop(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device.supports_turn_off:
        pytest.skip("Device doesn't support turn_off")
    with patch.object(
        type(fan_fixture.device),
        "is_on",
        new_callable=PropertyMock(return_value=False),
    ):
        respx_mock.route(dotstar).mock(resp_200)
        await fan_fixture.device.turn_off()
        assert len(respx_mock.calls) == 0


def test_property_supports_presets(fan_fixture: FanFixture) -> None:
    assert isinstance(fan_fixture.device.supports_presets, bool)


def test_property_preset_modes(fan_fixture: FanFixture) -> None:
    if fan_fixture.device.supports_presets:
        assert isinstance(fan_fixture.device.preset_modes, list)
        assert len(fan_fixture.device.preset_modes) > 0
    else:
        with pytest.raises(AqualinkOperationNotSupportedException):
            _ = fan_fixture.device.preset_modes


def test_property_preset_mode(fan_fixture: FanFixture) -> None:
    if fan_fixture.device.supports_presets:
        assert fan_fixture.device.preset_mode is None or isinstance(
            fan_fixture.device.preset_mode, str
        )
    else:
        with pytest.raises(AqualinkOperationNotSupportedException):
            _ = fan_fixture.device.preset_mode


def test_property_supports_percentage(fan_fixture: FanFixture) -> None:
    assert isinstance(fan_fixture.device.supports_percentage, bool)


async def test_set_percentage_0(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device.supports_percentage:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await fan_fixture.device.set_percentage(0)
        return
    respx_mock.route(dotstar).mock(resp_200)
    await fan_fixture.device.set_percentage(0)
    assert len(respx_mock.calls) > 0


async def test_set_percentage_50(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device.supports_percentage:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await fan_fixture.device.set_percentage(50)
        return
    respx_mock.route(dotstar).mock(resp_200)
    await fan_fixture.device.set_percentage(50)
    assert len(respx_mock.calls) > 0


async def test_set_percentage_100(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device.supports_percentage:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await fan_fixture.device.set_percentage(100)
        return
    respx_mock.route(dotstar).mock(resp_200)
    await fan_fixture.device.set_percentage(100)
    assert len(respx_mock.calls) > 0


async def test_set_percentage_invalid_negative(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device.supports_percentage:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await fan_fixture.device.set_percentage(-1)
        return
    respx_mock.route(dotstar).mock(resp_200)
    with pytest.raises(AqualinkInvalidParameterException):
        await fan_fixture.device.set_percentage(-1)
    assert len(respx_mock.calls) == 0


async def test_set_percentage_invalid_150(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device.supports_percentage:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await fan_fixture.device.set_percentage(150)
        return
    respx_mock.route(dotstar).mock(resp_200)
    with pytest.raises(AqualinkInvalidParameterException):
        await fan_fixture.device.set_percentage(150)
    assert len(respx_mock.calls) == 0


async def test_set_preset_mode(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device.supports_presets:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await fan_fixture.device.set_preset_mode("any")
        return
    respx_mock.route(dotstar).mock(resp_200)
    preset = fan_fixture.device.preset_modes[0]
    await fan_fixture.device.set_preset_mode(preset)
    assert len(respx_mock.calls) > 0


async def test_set_preset_mode_invalid(
    fan_fixture: FanFixture, respx_mock: respx.router.MockRouter
) -> None:
    if not fan_fixture.device.supports_presets:
        with pytest.raises(AqualinkOperationNotSupportedException):
            await fan_fixture.device.set_preset_mode("nonexistent")
        return
    respx_mock.route(dotstar).mock(resp_200)
    with pytest.raises(AqualinkInvalidParameterException):
        await fan_fixture.device.set_preset_mode("nonexistent_preset")
    assert len(respx_mock.calls) == 0


def test_from_data(fan_fixture: FanFixture) -> None:
    if fan_fixture.expected_class is not None:
        assert isinstance(fan_fixture.device, fan_fixture.expected_class)
