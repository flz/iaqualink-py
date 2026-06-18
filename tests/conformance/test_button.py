"""Conformance tests for AqualinkButton contract."""

from __future__ import annotations

import respx
import respx.router

from iaqualink.device import AqualinkButton

from .conftest import dotstar, resp_200
from .fixtures import ButtonFixture


def test_inheritance(button_fixture: ButtonFixture) -> None:
    assert isinstance(button_fixture.device, AqualinkButton)


async def test_press(
    button_fixture: ButtonFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    await button_fixture.device.press()
    assert len(respx_mock.calls) > 0


def test_from_data(button_fixture: ButtonFixture) -> None:
    if button_fixture.expected_class is not None:
        assert isinstance(button_fixture.device, button_fixture.expected_class)
