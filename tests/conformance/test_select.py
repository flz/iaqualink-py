"""Conformance tests for AqualinkSelect contract."""

from __future__ import annotations

import pytest
import respx
import respx.router

from iaqualink.device import AqualinkSelect
from iaqualink.exception import AqualinkInvalidParameterException

from .conftest import dotstar, resp_200
from .fixtures import SelectFixture


def test_inheritance(select_fixture: SelectFixture) -> None:
    assert isinstance(select_fixture.device, AqualinkSelect)


def test_property_options(select_fixture: SelectFixture) -> None:
    assert isinstance(select_fixture.device.options, list)
    assert all(isinstance(o, str) for o in select_fixture.device.options)


def test_property_current_option(select_fixture: SelectFixture) -> None:
    current = select_fixture.device.current_option
    assert current is None or current in select_fixture.device.options


async def test_select_valid_option(
    select_fixture: SelectFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    option = select_fixture.device.options[0]
    await select_fixture.device.select_option(option)
    assert len(respx_mock.calls) > 0


async def test_select_invalid_option(
    select_fixture: SelectFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(dotstar).mock(resp_200)
    with pytest.raises(AqualinkInvalidParameterException):
        await select_fixture.device.select_option("not-a-real-option")
    assert len(respx_mock.calls) == 0


def test_from_data(select_fixture: SelectFixture) -> None:
    if select_fixture.expected_class is not None:
        assert isinstance(select_fixture.device, select_fixture.expected_class)


# ---------------------------------------------------------------------------
# Template-method regression tests (no HTTP mocking — pure logic)
# ---------------------------------------------------------------------------


def _make_select_for_template(options: list[str]) -> AqualinkSelect:
    """Concrete AqualinkSelect for testing select_option template logic directly.

    Skips AqualinkDevice.__init__ — no system/data needed for template tests.
    Records each accepted option in ._calls.
    """
    calls: list[str] = []

    class _S(AqualinkSelect):
        def __init__(self) -> None:
            pass  # skip AqualinkDevice.__init__

        @property
        def label(self) -> str:
            return "S"

        @property
        def name(self) -> str:
            return "s"

        @property
        def manufacturer(self) -> str:
            return ""

        @property
        def model(self) -> str:
            return ""

        @property
        def current_option(self) -> str | None:
            return None

        @property
        def options(self) -> list[str]:
            return options

        async def _select_option(self, option: str) -> None:
            calls.append(option)

    s = _S()
    s._calls = calls  # type: ignore[attr-defined]  # ty: ignore
    return s


async def test_select_option_template_valid() -> None:
    s = _make_select_for_template(["heat", "chill"])
    await s.select_option("chill")
    assert s._calls == ["chill"]  # type: ignore[attr-defined]  # ty: ignore


async def test_select_option_template_invalid_raises() -> None:
    s = _make_select_for_template(["heat", "chill"])
    with pytest.raises(AqualinkInvalidParameterException):
        await s.select_option("auto")
    assert s._calls == []  # type: ignore[attr-defined]  # ty: ignore
