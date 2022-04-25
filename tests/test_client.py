from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest

from iaqualink.client import AqualinkClient
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)

from .base import TestBase
from .common import async_noop, async_raises

LOGIN_DATA = {
    "id": "id",
    "authentication_token": "token",
    "session_id": "session_id",
}


class TestAqualinkClient(TestBase):
    def setUp(self) -> None:
        super().setUp()

    @patch.object(AqualinkClient, "login")
    async def test_context_manager(self, mock_login) -> None:
        mock_login.return_value = async_noop

        async with self.client:
            pass

    @patch.object(AqualinkClient, "login")
    async def test_context_manager_login_exception(self, mock_login) -> None:
        mock_login.side_effect = async_raises(AqualinkServiceException)

        with pytest.raises(AqualinkServiceException):
            async with self.client:
                pass

    @patch("iaqualink.client.AqualinkClient.login", async_noop)
    async def test_context_manager_with_client(self) -> None:
        client = httpx.AsyncClient()
        async with AqualinkClient("user", "pass", httpx_client=client):
            pass

        # Clean up.
        await client.aclose()

    @patch("httpx.AsyncClient.request")
    async def test_login_success(self, mock_request) -> None:
        mock_request.return_value.status_code = 200
        mock_request.return_value.json = MagicMock(return_value=LOGIN_DATA)

        assert self.client.logged is False

        await self.client.login()

        assert self.client.logged is True

    @patch("httpx.AsyncClient.request")
    async def test_login_failed(self, mock_request) -> None:
        mock_request.return_value.status_code = 401

        assert self.client.logged is False

        with pytest.raises(AqualinkServiceException):
            await self.client.login()

        assert self.client.logged is False

    @patch("httpx.AsyncClient.request")
    async def test_login_exception(self, mock_request) -> None:
        mock_request.return_value.status_code = 500

        assert self.client.logged is False

        with pytest.raises(AqualinkServiceException):
            await self.client.login()

        assert self.client.logged is False

    @patch("httpx.AsyncClient.request")
    async def test_unexpectedly_logged_out(self, mock_request) -> None:
        mock_request.return_value.status_code = 200
        mock_request.return_value.json = MagicMock(return_value=LOGIN_DATA)

        await self.client.login()

        assert self.client.logged is True

        mock_request.return_value.status_code = 401
        mock_request.return_value.json = MagicMock(return_value={})

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await self.client.get_systems()

        assert self.client.logged is False

    @patch("httpx.AsyncClient.request")
    async def test_systems_request_system_unsupported(
        self, mock_request
    ) -> None:
        mock_request.return_value.status_code = 200
        mock_request.return_value.json = MagicMock(return_value=LOGIN_DATA)

        await self.client.login()

        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = [
            {
                "device_type": "foo",
                "serial_number": "SN123456",
            }
        ]

        systems = await self.client.get_systems()
        assert len(systems) == 0

    @patch("httpx.AsyncClient.request")
    async def test_systems_request(self, mock_request) -> None:
        mock_request.return_value.status_code = 200
        mock_request.return_value.json = MagicMock(return_value=LOGIN_DATA)

        await self.client.login()

        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = [
            {
                "device_type": "iaqua",
                "serial_number": "SN123456",
            }
        ]

        systems = await self.client.get_systems()
        assert len(systems) == 1

    @patch("httpx.AsyncClient.request")
    async def test_systems_request_unauthorized(self, mock_request) -> None:
        mock_request.return_value.status_code = 404

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await self.client.get_systems()
