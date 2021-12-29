from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

import httpx
import pytest

from iaqualink.client import AqualinkClient
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)
from iaqualink.system import AqualinkSystem

from .common import async_noop, async_raises

LOGIN_DATA = {
    "id": "id",
    "authentication_token": "token",
    "session_id": "session_id",
}


class TestAqualinkClient(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.aqualink = AqualinkClient("user", "pass")

    async def asyncTearDown(self) -> None:
        await self.aqualink.close()

    @patch.object(AqualinkClient, "login")
    async def test_context_manager(self, mock_login):
        mock_login.return_value = async_noop

        async with self.aqualink:
            pass

    @patch.object(AqualinkClient, "login")
    async def test_context_manager_login_exception(self, mock_login):
        mock_login.side_effect = async_raises(AqualinkServiceException)

        with pytest.raises(AqualinkServiceException):
            async with self.aqualink:
                pass

    @patch("iaqualink.client.AqualinkClient.login", async_noop)
    async def test_context_manager_with_client(self):
        client = httpx.AsyncClient()
        async with AqualinkClient("user", "pass", httpx_client=client):
            pass

        # Clean up.
        await client.aclose()

    @patch("httpx.AsyncClient.request")
    async def test_login_success(self, mock_request):
        mock_request.return_value.status_code = 200
        mock_request.return_value.json = MagicMock(return_value=LOGIN_DATA)

        assert self.aqualink.logged is False

        await self.aqualink.login()

        assert self.aqualink.logged is True

    @patch("httpx.AsyncClient.request")
    async def test_login_failed(self, mock_request):
        mock_request.return_value.status_code = 401

        assert self.aqualink.logged is False

        with pytest.raises(AqualinkServiceException):
            await self.aqualink.login()

        assert self.aqualink.logged is False

    @patch("httpx.AsyncClient.request")
    async def test_login_exception(self, mock_request):
        mock_request.return_value.status_code = 500

        assert self.aqualink.logged is False

        with pytest.raises(AqualinkServiceException):
            await self.aqualink.login()

        assert self.aqualink.logged is False

    @patch("httpx.AsyncClient.request")
    async def test_unexpectedly_logged_out(self, mock_request):
        mock_request.return_value.status_code = 200
        mock_request.return_value.json = MagicMock(return_value=LOGIN_DATA)

        await self.aqualink.login()

        mock_request.return_value.status_code = 401
        mock_request.return_value.json = MagicMock(return_value={})

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await self.aqualink.get_systems()

        assert self.aqualink.logged is False

    @patch("iaqualink.system.AqualinkSystem.from_data")
    @patch("httpx.AsyncClient.request")
    async def test_systems_request(self, mock_request, mock_from_data):
        mock_request.return_value.status_code = 200
        mock_request.return_value.json = MagicMock(return_value={})

        mock_from_data.return_value = AqualinkSystem(
            self.aqualink, data={"serial_number": "xxx"}
        )

        await self.aqualink.get_systems()

    @patch("httpx.AsyncClient.request")
    async def test_systems_request_unauthorized(self, mock_request):
        mock_request.return_value.status_code = 404

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await self.aqualink.get_systems()

    @patch("httpx.AsyncClient.request")
    async def test_home_request(self, mock_request):
        mock_request.return_value.status_code = 200

        await self.aqualink.send_home_screen_request(serial="xxx")

    @patch("httpx.AsyncClient.request")
    async def test_home_request_unauthorized(self, mock_request):
        mock_request.return_value.status_code = 401

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await self.aqualink.send_home_screen_request(serial="xxx")

    @patch("httpx.AsyncClient.request")
    async def test_devices_request(self, mock_request):
        mock_request.return_value.status_code = 200

        await self.aqualink.send_devices_screen_request(serial="xxx")

    @patch("httpx.AsyncClient.request")
    async def test_devices_request_unauthorized(self, mock_request):
        mock_request.return_value.status_code = 401

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await self.aqualink.send_devices_screen_request(serial="xxx")
