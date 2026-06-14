"""Conformance tests for AqualinkSystem contract."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import respx
import respx.router

from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
)
from iaqualink.system import SystemStatus

from .conftest import dotstar as _dotstar
from .conftest import resp_200 as _resp_200
from .fixtures import SystemFixture


def test_property_name(system_fixture: SystemFixture) -> None:
    assert isinstance(system_fixture.system.name, str)


def test_property_serial(system_fixture: SystemFixture) -> None:
    assert isinstance(system_fixture.system.serial, str)


def test_property_type(system_fixture: SystemFixture) -> None:
    assert system_fixture.system.type == system_fixture.system.__class__.NAME


def test_repr(system_fixture: SystemFixture) -> None:
    r = repr(system_fixture.system)
    assert system_fixture.system.name in r
    assert system_fixture.system.serial in r


def test_property_status_translated(system_fixture: SystemFixture) -> None:
    assert isinstance(system_fixture.system.status_translated, str)


def test_property_devices(system_fixture: SystemFixture) -> None:
    assert isinstance(system_fixture.system.devices, dict)


def test_property_supported(system_fixture: SystemFixture) -> None:
    assert isinstance(system_fixture.system.supported, bool)


def test_from_data(system_fixture: SystemFixture) -> None:
    if system_fixture.expected_class is not None:
        assert isinstance(system_fixture.system, system_fixture.expected_class)


async def test_refresh_success(
    system_fixture: SystemFixture, respx_mock: respx.router.MockRouter
) -> None:
    resp = httpx.Response(status_code=200, json=system_fixture.refresh_response)
    respx_mock.route(_dotstar).mock(resp)
    await system_fixture.system.refresh()
    assert len(respx_mock.calls) > 0
    if system_fixture.expected_online_status is not None:
        assert (
            system_fixture.system.status
            is system_fixture.expected_online_status
        )


async def test_refresh_service_exception(
    system_fixture: SystemFixture, respx_mock: respx.router.MockRouter
) -> None:
    resp_500 = httpx.Response(status_code=500)
    respx_mock.route(_dotstar).mock(resp_500)
    with pytest.raises(AqualinkServiceException):
        await system_fixture.system.refresh()
    assert system_fixture.system.status is SystemStatus.DISCONNECTED


async def test_refresh_request_unauthorized(
    system_fixture: SystemFixture, respx_mock: respx.router.MockRouter
) -> None:
    resp_401 = httpx.Response(status_code=401)
    respx_mock.route(_dotstar).mock(resp_401)
    with pytest.raises(AqualinkServiceUnauthorizedException):
        await system_fixture.system.refresh()
    assert len(respx_mock.calls) > 0


async def test_refresh_throttled(
    system_fixture: SystemFixture, respx_mock: respx.router.MockRouter
) -> None:
    resp_429 = httpx.Response(status_code=429)
    respx_mock.route(_dotstar).mock(resp_429)
    with pytest.raises(AqualinkServiceThrottledException):
        await system_fixture.system.refresh()
    assert system_fixture.system.status is SystemStatus.UNKNOWN


async def test_refresh_retries_after_401(
    system_fixture: SystemFixture, respx_mock: respx.router.MockRouter
) -> None:
    """First request returns 401, reauth succeeds, retry returns 200."""
    resp_401 = httpx.Response(status_code=401)
    resp_ok = httpx.Response(
        status_code=200, json=system_fixture.refresh_response
    )
    respx_mock.route(_dotstar).mock(
        side_effect=[resp_401, resp_ok, resp_ok, resp_ok]
    )

    with patch.object(
        system_fixture.system.aqualink,
        "_refresh_auth",
        new_callable=AsyncMock,
    ) as mock_refresh:
        await system_fixture.system.refresh()

    mock_refresh.assert_awaited_once()
    if system_fixture.expected_online_status is not None:
        assert (
            system_fixture.system.status
            is system_fixture.expected_online_status
        )


async def test_refresh_retries_only_once_on_repeated_401(
    system_fixture: SystemFixture, respx_mock: respx.router.MockRouter
) -> None:
    """Both initial request and retry return 401 — raises after single reauth."""
    resp_401 = httpx.Response(status_code=401)
    respx_mock.route(_dotstar).mock(resp_401)

    with (
        patch.object(
            system_fixture.system.aqualink,
            "_refresh_auth",
            new_callable=AsyncMock,
        ) as mock_refresh,
        pytest.raises(AqualinkServiceUnauthorizedException),
    ):
        await system_fixture.system.refresh()

    mock_refresh.assert_awaited_once()


async def test_get_devices(
    system_fixture: SystemFixture, respx_mock: respx.router.MockRouter
) -> None:
    respx_mock.route(_dotstar).mock(_resp_200)
    system_fixture.system.devices = {"foo": MagicMock()}
    await system_fixture.system.get_devices()
    assert len(respx_mock.calls) == 0


async def test_get_devices_needs_update(
    system_fixture: SystemFixture, respx_mock: respx.router.MockRouter
) -> None:
    resp = httpx.Response(status_code=200, json=system_fixture.refresh_response)
    respx_mock.route(_dotstar).mock(resp)
    await system_fixture.system.get_devices()
    assert len(respx_mock.calls) > 0
