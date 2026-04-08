from __future__ import annotations

from datetime import datetime, timedelta, timezone
from email.utils import format_datetime
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from iaqualink.client import AqualinkClient
from iaqualink.const import (
    RETRY_AFTER_MAX_DELAY,
    RETRY_MAX_ATTEMPTS,
    RETRY_MAX_DELAY,
)
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

LOGIN_DATA_WITH_REFRESH = {
    "id": "id",
    "authentication_token": "token",
    "session_id": "session_id",
    "userPoolOAuth": {
        "IdToken": "userPoolOAuth:IdToken",
        "RefreshToken": "userPoolOAuth:RefreshToken",
    },
}

REFRESH_RESPONSE_DATA = {
    "id": "id",
    "authentication_token": "new-token",
    "session_id": "new-session-id",
    "userPoolOAuth": {
        "IdToken": "new-id-token",
        "RefreshToken": "userPoolOAuth:RefreshToken",
    },
}


def _make_resp(status: int, data: dict | None = None) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.reason_phrase = httpx.codes.get_reason_phrase(status)
    if data is not None:
        r.json = MagicMock(return_value=data)
    if status == httpx.codes.TOO_MANY_REQUESTS:
        r.headers = httpx.Headers({})
    return r


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

    # The 429-retry tests use @patch("httpx.AsyncClient.request") rather
    # than respx because respx intercepts at transport level, before the
    # retry loop in send_request() — we need to control per-call
    # responses (side_effect) and inspect asyncio.sleep calls.
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
        future = datetime.now(tz=timezone.utc) + timedelta(days=365)
        resp_429 = MagicMock()
        resp_429.status_code = httpx.codes.TOO_MANY_REQUESTS
        resp_429.reason_phrase = "Too Many Requests"
        resp_429.headers = httpx.Headers(
            {"retry-after": format_datetime(future, usegmt=True)}
        )

        resp_200 = MagicMock()
        resp_200.status_code = httpx.codes.OK
        resp_200.reason_phrase = "OK"
        resp_200.json = MagicMock(return_value={})

        mock_request.side_effect = [resp_429, resp_200]

        r = await self.client.send_request("https://example.com")
        assert r.status_code == httpx.codes.OK
        # Future HTTP-date is parsed and capped at RETRY_AFTER_MAX_DELAY.
        mock_sleep.assert_called_once_with(RETRY_AFTER_MAX_DELAY)

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
        mock_sleep.assert_called_once_with(RETRY_AFTER_MAX_DELAY)

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

    @patch("iaqualink.client.asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.request")
    async def test_429_retry_after_past_date(
        self, mock_request, mock_sleep
    ) -> None:
        resp_429 = MagicMock()
        resp_429.status_code = httpx.codes.TOO_MANY_REQUESTS
        resp_429.reason_phrase = "Too Many Requests"
        resp_429.headers = httpx.Headers(
            {"retry-after": "Wed, 21 Oct 2015 07:28:00 GMT"}
        )

        resp_200 = MagicMock()
        resp_200.status_code = httpx.codes.OK
        resp_200.reason_phrase = "OK"
        resp_200.json = MagicMock(return_value={})

        mock_request.side_effect = [resp_429, resp_200]

        r = await self.client.send_request("https://example.com")
        assert r.status_code == httpx.codes.OK
        # Past date yields negative delay, so falls back to
        # exponential backoff.
        mock_sleep.assert_called_once()
        delay = mock_sleep.call_args[0][0]
        assert 0 <= delay <= RETRY_MAX_DELAY

    @patch("iaqualink.client.asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.request")
    async def test_429_retry_after_unparseable(
        self, mock_request, mock_sleep
    ) -> None:
        resp_429 = MagicMock()
        resp_429.status_code = httpx.codes.TOO_MANY_REQUESTS
        resp_429.reason_phrase = "Too Many Requests"
        resp_429.headers = httpx.Headers({"retry-after": "totally-invalid"})

        resp_200 = MagicMock()
        resp_200.status_code = httpx.codes.OK
        resp_200.reason_phrase = "OK"
        resp_200.json = MagicMock(return_value={})

        mock_request.side_effect = [resp_429, resp_200]

        r = await self.client.send_request("https://example.com")
        assert r.status_code == httpx.codes.OK
        # Unparseable header falls back to exponential backoff.
        mock_sleep.assert_called_once()
        delay = mock_sleep.call_args[0][0]
        assert 0 <= delay <= RETRY_MAX_DELAY

    @patch("httpx.AsyncClient.request")
    async def test_refresh_on_401_retries_and_succeeds(
        self, mock_request
    ) -> None:
        mock_request.side_effect = [
            _make_resp(200, LOGIN_DATA_WITH_REFRESH),  # login
            _make_resp(401),  # original request → 401
            _make_resp(200, REFRESH_RESPONSE_DATA),  # refresh token call
            _make_resp(200, {}),  # retry of original request
        ]

        await self.client.login()
        r = await self.client.send_request("https://example.com")

        assert r.status_code == httpx.codes.OK
        assert mock_request.call_count == 4

    @patch("httpx.AsyncClient.request")
    async def test_refresh_updates_tokens(self, mock_request) -> None:
        mock_request.side_effect = [
            _make_resp(200, LOGIN_DATA_WITH_REFRESH),
            _make_resp(401),
            _make_resp(200, REFRESH_RESPONSE_DATA),
            _make_resp(200, {}),
        ]

        await self.client.login()
        await self.client.send_request("https://example.com")

        assert self.client.id_token == "new-id-token"
        assert self.client._token == "new-token"
        assert self.client._user_id == "id"
        assert self.client.client_id == "new-session-id"
        assert self.client.logged is True

    @patch("httpx.AsyncClient.request")
    async def test_refresh_fallback_to_login_on_refresh_failure(
        self, mock_request
    ) -> None:
        mock_request.side_effect = [
            _make_resp(200, LOGIN_DATA_WITH_REFRESH),  # initial login
            _make_resp(401),  # original request → 401
            _make_resp(401),  # refresh request → 401
            _make_resp(200, LOGIN_DATA_WITH_REFRESH),  # fallback full login
            _make_resp(200, {}),  # retry of original request
        ]

        await self.client.login()
        r = await self.client.send_request("https://example.com")

        assert r.status_code == httpx.codes.OK
        assert mock_request.call_count == 5
        assert self.client.logged is True

    @patch("iaqualink.client.asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.request")
    async def test_refresh_retry_429_raises_throttled(
        self, mock_request, mock_sleep
    ) -> None:
        # After a token refresh the retry re-enters the main loop, so 429
        # responses benefit from the same backoff/retry budget as normal.
        mock_request.side_effect = [
            _make_resp(200, LOGIN_DATA_WITH_REFRESH),  # login
            _make_resp(401),  # original → 401
            _make_resp(200, REFRESH_RESPONSE_DATA),  # refresh token
            *[_make_resp(429)] * RETRY_MAX_ATTEMPTS,  # all retries exhausted
        ]

        await self.client.login()
        with pytest.raises(AqualinkServiceThrottledException):
            await self.client.send_request("https://example.com")
        assert mock_sleep.call_count == RETRY_MAX_ATTEMPTS - 1

    @patch("iaqualink.client.asyncio.sleep", new_callable=AsyncMock)
    @patch("httpx.AsyncClient.request")
    async def test_refresh_retry_gets_full_429_budget(
        self, mock_request, mock_sleep
    ) -> None:
        # 429s received before the 401 must not reduce the retry budget
        # available to the post-refresh request.
        pre_refresh_429s = 2
        mock_request.side_effect = [
            _make_resp(200, LOGIN_DATA_WITH_REFRESH),  # login
            *[_make_resp(429)] * pre_refresh_429s,  # rate-limited before 401
            _make_resp(401),  # original → triggers refresh
            _make_resp(200, REFRESH_RESPONSE_DATA),  # refresh token
            *[_make_resp(429)]
            * RETRY_MAX_ATTEMPTS,  # post-refresh: full budget
        ]

        await self.client.login()
        with pytest.raises(AqualinkServiceThrottledException):
            await self.client.send_request("https://example.com")
        # pre-refresh sleeps + post-refresh sleeps (full budget)
        assert mock_sleep.call_count == pre_refresh_429s + (
            RETRY_MAX_ATTEMPTS - 1
        )

    @patch("httpx.AsyncClient.request")
    async def test_refresh_retry_500_raises_service_exception(
        self, mock_request
    ) -> None:
        mock_request.side_effect = [
            _make_resp(200, LOGIN_DATA_WITH_REFRESH),
            _make_resp(401),
            _make_resp(200, REFRESH_RESPONSE_DATA),
            _make_resp(500),  # retry after refresh gets a server error
        ]

        await self.client.login()
        with pytest.raises(AqualinkServiceException) as exc_info:
            await self.client.send_request("https://example.com")
        assert not isinstance(
            exc_info.value, AqualinkServiceUnauthorizedException
        )

    async def test_refresh_auth_propagates_throttled(self) -> None:
        self.client._refresh_token = "some-refresh-token"
        with patch.object(
            self.client,
            "_send_refresh_request",
            side_effect=AqualinkServiceThrottledException("Rate limited"),
        ):
            with pytest.raises(AqualinkServiceThrottledException):
                await self.client._refresh_auth()

    @patch("httpx.AsyncClient.request")
    async def test_refresh_throttled_propagates_from_send_request(
        self, mock_request
    ) -> None:
        mock_request.side_effect = [
            _make_resp(200, LOGIN_DATA_WITH_REFRESH),
            _make_resp(401),
        ]

        await self.client.login()
        with patch.object(
            self.client,
            "_refresh_auth",
            side_effect=AqualinkServiceThrottledException("Rate limited"),
        ):
            with pytest.raises(AqualinkServiceThrottledException):
                await self.client.send_request("https://example.com")

    @patch("httpx.AsyncClient.request")
    async def test_refresh_updates_bearer_auth_header_on_retry(
        self, mock_request
    ) -> None:
        mock_request.side_effect = [
            _make_resp(200, LOGIN_DATA_WITH_REFRESH),
            _make_resp(401),
            _make_resp(200, REFRESH_RESPONSE_DATA),
            _make_resp(200, {}),
        ]

        await self.client.login()
        await self.client.send_request(
            "https://example.com",
            headers={"Authorization": f"Bearer {self.client.id_token}"},
        )

        # The retry (4th call) must use the new token, not the stale one.
        retry_headers = mock_request.call_args_list[3][1]["headers"]
        assert retry_headers["Authorization"] == "Bearer new-id-token"

    @patch("httpx.AsyncClient.request")
    async def test_refresh_updates_raw_auth_header_on_retry(
        self, mock_request
    ) -> None:
        mock_request.side_effect = [
            _make_resp(200, LOGIN_DATA_WITH_REFRESH),
            _make_resp(401),
            _make_resp(200, REFRESH_RESPONSE_DATA),
            _make_resp(200, {}),
        ]

        await self.client.login()
        # eXO-style: raw token without Bearer prefix
        await self.client.send_request(
            "https://example.com",
            headers={"Authorization": self.client.id_token},
        )

        retry_headers = mock_request.call_args_list[3][1]["headers"]
        assert retry_headers["Authorization"] == "new-id-token"

    @patch("httpx.AsyncClient.request")
    async def test_401_without_refresh_token_raises_immediately(
        self, mock_request
    ) -> None:
        # When no refresh token is available, 401 raises without any retry.
        mock_request.side_effect = [
            _make_resp(200, LOGIN_DATA),  # login — no RefreshToken in response
            _make_resp(401),
        ]

        await self.client.login()
        with pytest.raises(AqualinkServiceUnauthorizedException):
            await self.client.send_request("https://example.com")
        assert mock_request.call_count == 2

    @patch("httpx.AsyncClient.request")
    async def test_refresh_retains_existing_token_when_none_returned(
        self, mock_request
    ) -> None:
        # If the refresh response omits RefreshToken, keep the existing one.
        refresh_no_new_token = {
            "id": "id",
            "authentication_token": "new-token",
            "session_id": "new-session-id",
            "userPoolOAuth": {"IdToken": "new-id-token"},
        }
        mock_request.side_effect = [
            _make_resp(200, LOGIN_DATA_WITH_REFRESH),
            _make_resp(401),
            _make_resp(200, refresh_no_new_token),
            _make_resp(200, {}),
        ]

        await self.client.login()
        original_refresh_token = self.client._refresh_token
        await self.client.send_request("https://example.com")

        assert self.client._refresh_token == original_refresh_token
