"""Conformance tests for AqualinkSwitch contract."""

from __future__ import annotations

import respx
import respx.router

from iaqualink.device import AqualinkSwitch

from .conftest import dotstar, resp_200
from .fixtures import SwitchFixture


def test_inheritance(switch_fixture: SwitchFixture) -> None:
    assert isinstance(switch_fixture.device_on, AqualinkSwitch)


def test_property_is_on_true(switch_fixture: SwitchFixture) -> None:
    assert switch_fixture.device_on.is_on is True


def test_property_is_on_false(switch_fixture: SwitchFixture) -> None:
    assert switch_fixture.device_off.is_on is False


async def test_turn_on(
    switch_fixture: SwitchFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    await switch_fixture.device_off.turn_on()
    assert len(respx_mock.calls) > 0


async def test_turn_on_noop(
    switch_fixture: SwitchFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    await switch_fixture.device_on.turn_on()
    if switch_fixture.has_noop_guard:
        assert len(respx_mock.calls) == 0
    else:
        assert len(respx_mock.calls) > 0


async def test_turn_off(
    switch_fixture: SwitchFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    await switch_fixture.device_on.turn_off()
    assert len(respx_mock.calls) > 0


async def test_turn_off_noop(
    switch_fixture: SwitchFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    await switch_fixture.device_off.turn_off()
    if switch_fixture.has_noop_guard:
        assert len(respx_mock.calls) == 0
    else:
        assert len(respx_mock.calls) > 0


def test_from_data(switch_fixture: SwitchFixture) -> None:
    if switch_fixture.expected_class is not None:
        assert isinstance(
            switch_fixture.device_on, switch_fixture.expected_class
        )
