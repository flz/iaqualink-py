from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from iaqualink.client import AqualinkClient
from iaqualink.const import RETRY_MAX_ATTEMPTS, RETRY_MAX_DELAY
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
)

from .base import TestBase
from .common import async_noop, async_raises

LOGIN_DATA = {
    "id": "id",
    "authentication_token": "token",
    "session_id": "session_id",
    "userPoolOAuth": {"IdToken": "userPoolOAuth:IdToken"},
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

    @patch("iaqualink.client.asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.request")
    async def test_429_retry_then_success(
        self, mock_request, mock_sleep
    ) -> None:
        resp_429 = MagicMock()
        resp_429.status_code = httpx.codes.TOO_MANY_REQUESTS
        resp_429.reason_phrase = "Too Many Requests"
        resp_429.headers = httpx.Headers({})

        resp_200 = MagicMock()
        resp_200.status_code = httpx.codes.OK
        resp_200.reason_phrase = "OK"
        resp_200.json = MagicMock(return_value={})

        mock_request.side_effect = [resp_429, resp_200]

        r = await self.client.send_request("https://example.com")
        assert r.status_code == httpx.codes.OK
        assert mock_request.call_count == 2
        mock_sleep.assert_called_once()

    @patch("iaqualink.client.asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.request")
    async def test_429_retry_after_header(
        self, mock_request, mock_sleep
    ) -> None:
        resp_429 = MagicMock()
        resp_429.status_code = httpx.codes.TOO_MANY_REQUESTS
        resp_429.reason_phrase = "Too Many Requests"
        resp_429.headers = httpx.Headers({"retry-after": "5"})

        resp_200 = MagicMock()
        resp_200.status_code = httpx.codes.OK
        resp_200.reason_phrase = "OK"
        resp_200.json = MagicMock(return_value={})

        mock_request.side_effect = [resp_429, resp_200]

        r = await self.client.send_request("https://example.com")
        assert r.status_code == httpx.codes.OK
        mock_sleep.assert_called_once_with(5.0)

    @patch("iaqualink.client.asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.request")
    async def test_429_retries_exhausted(
        self, mock_request, mock_sleep
    ) -> None:
        resp_429 = MagicMock()
        resp_429.status_code = httpx.codes.TOO_MANY_REQUESTS
        resp_429.reason_phrase = "Too Many Requests"
        resp_429.headers = httpx.Headers({})

        mock_request.return_value = resp_429

        with pytest.raises(AqualinkServiceThrottledException):
            await self.client.send_request("https://example.com")

        assert mock_request.call_count == RETRY_MAX_ATTEMPTS
        assert mock_sleep.call_count == RETRY_MAX_ATTEMPTS - 1

    @patch("iaqualink.client.asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.request")
    async def test_500_not_retried(self, mock_request, mock_sleep) -> None:
        mock_request.return_value.status_code = (
            httpx.codes.INTERNAL_SERVER_ERROR
        )
        mock_request.return_value.reason_phrase = "Internal Server Error"

        with pytest.raises(AqualinkServiceException):
            await self.client.send_request("https://example.com")

        assert mock_request.call_count == 1
        mock_sleep.assert_not_called()

    @patch("iaqualink.client.asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.request")
    async def test_401_not_retried(self, mock_request, mock_sleep) -> None:
        mock_request.return_value.status_code = httpx.codes.UNAUTHORIZED

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await self.client.send_request("https://example.com")

        assert mock_request.call_count == 1
        mock_sleep.assert_not_called()

    @patch("iaqualink.client.asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.request")
    async def test_429_retry_after_http_date(
        self, mock_request, mock_sleep
    ) -> None:
        resp_429 = MagicMock()
        resp_429.status_code = httpx.codes.TOO_MANY_REQUESTS
        resp_429.reason_phrase = "Too Many Requests"
        resp_429.headers = httpx.Headers(
            {"retry-after": "Wed, 21 Oct 2026 07:28:00 GMT"}
        )

        resp_200 = MagicMock()
        resp_200.status_code = httpx.codes.OK
        resp_200.reason_phrase = "OK"
        resp_200.json = MagicMock(return_value={})

        mock_request.side_effect = [resp_429, resp_200]

        r = await self.client.send_request("https://example.com")
        assert r.status_code == httpx.codes.OK
        # HTTP-date can't be parsed as float, so falls back to
        # exponential backoff.
        mock_sleep.assert_called_once()
        delay = mock_sleep.call_args[0][0]
        assert delay > 0

    @patch("iaqualink.client.asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.request")
    async def test_429_retry_after_capped_at_max_delay(
        self, mock_request, mock_sleep
    ) -> None:
        resp_429 = MagicMock()
        resp_429.status_code = httpx.codes.TOO_MANY_REQUESTS
        resp_429.reason_phrase = "Too Many Requests"
        resp_429.headers = httpx.Headers({"retry-after": "999"})

        resp_200 = MagicMock()
        resp_200.status_code = httpx.codes.OK
        resp_200.reason_phrase = "OK"
        resp_200.json = MagicMock(return_value={})

        mock_request.side_effect = [resp_429, resp_200]

        r = await self.client.send_request("https://example.com")
        assert r.status_code == httpx.codes.OK
        mock_sleep.assert_called_once_with(RETRY_MAX_DELAY)

    @patch("iaqualink.client.asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.request")
    async def test_429_no_retry_when_disabled(
        self, mock_request, mock_sleep
    ) -> None:
        resp_429 = MagicMock()
        resp_429.status_code = httpx.codes.TOO_MANY_REQUESTS
        resp_429.reason_phrase = "Too Many Requests"
        resp_429.headers = httpx.Headers({})

        mock_request.return_value = resp_429

        with pytest.raises(AqualinkServiceThrottledException):
            await self.client.send_request("https://example.com", retry=False)

        assert mock_request.call_count == 1
        mock_sleep.assert_not_called()
