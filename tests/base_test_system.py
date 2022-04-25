import copy

import httpx
import pytest
import respx.router

from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)

from .base import TestBase, dotstar, resp_200


class TestBaseSystem(TestBase):
    def test_propery_name(self) -> None:
        assert isinstance(self.sut.name, str)

    def test_property_serial(self) -> None:
        assert isinstance(self.sut.name, str)

    def test_from_data(self) -> None:
        if sut_class := getattr(self, "sut_class", None):
            assert isinstance(self.sut, sut_class)

    @respx.mock
    async def test_update_success(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.update()
        assert len(respx_mock.calls) > 0
        self.respx_calls = copy.copy(respx_mock.calls)

    @respx.mock
    async def test_update_consecutive(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.update()
        respx_mock.reset()
        await self.sut.update()
        assert len(respx_mock.calls) == 0

    @respx.mock
    async def test_update_service_exception(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        resp_500 = httpx.Response(status_code=500)
        respx_mock.route(dotstar).mock(resp_500)
        with pytest.raises(AqualinkServiceException):
            await self.sut.update()
        self.respx_calls = copy.copy(respx_mock.calls)

    @respx.mock
    async def test_update_request_unauthorized(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        resp_401 = httpx.Response(status_code=401)
        respx_mock.route(dotstar).mock(resp_401)
        with pytest.raises(AqualinkServiceUnauthorizedException):
            await self.sut.update()
        assert len(respx_mock.calls) > 0
        self.respx_calls = copy.copy(respx_mock.calls)

    @respx.mock
    async def test_get_devices(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        self.sut.devices = {"foo": {}}
        await self.sut.get_devices()
        assert len(respx_mock.calls) == 0

    @respx.mock
    async def test_get_devices_needs_update(
        self, respx_mock: respx.router.MockRouter
    ) -> None:
        respx_mock.route(dotstar).mock(resp_200)
        await self.sut.get_devices()
        assert len(respx_mock.calls) > 0
        self.respx_calls = copy.copy(respx_mock.calls)
