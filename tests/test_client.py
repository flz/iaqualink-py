from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock, patch

import httpx
import pytest
import respx

from iaqualink.client import (
    AqualinkAuthState,
    AqualinkClient,
)
from iaqualink.const import (
    DEFAULT_REQUEST_TIMEOUT,
)
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
)
from iaqualink.system import UnsupportedSystem

from .base import TestBase
from .common import async_noop, async_raises

LOGIN_DATA = {
    "id": 1,
    "authentication_token": "token",
    "session_id": "session_id",
    "userPoolOAuth": {"IdToken": "userPoolOAuth:IdToken"},
}

LOGIN_DATA_WITH_REFRESH = {
    "id": 1,
    "authentication_token": "token",
    "session_id": "session_id",
    "userPoolOAuth": {
        "IdToken": "userPoolOAuth:IdToken",
        "RefreshToken": "userPoolOAuth:RefreshToken",
    },
}

REFRESH_RESPONSE_DATA = {
    "id": 1,
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
        r.text = json.dumps(data)
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

    async def test_auth_state_when_not_logged_in(self) -> None:
        assert self.client.auth_state is None

    @patch("httpx.AsyncClient.request")
    async def test_auth_state_when_logged_in(self, mock_request) -> None:
        mock_request.return_value = _make_resp(200, LOGIN_DATA_WITH_REFRESH)

        await self.client.login()

        expected = AqualinkAuthState(
            username="foo",
            client_id="session_id",
            authentication_token="token",
            user_id="1",
            id_token="userPoolOAuth:IdToken",
            refresh_token="userPoolOAuth:RefreshToken",
        )

        assert self.client.auth_state == expected

    async def test_auth_state_setter_accepts_none(self) -> None:
        self.client.auth_state = None

        assert self.client.logged is False
        assert self.client.auth_state is None

    def test_auth_state_from_dict_requires_all_fields(self) -> None:
        with pytest.raises(ValueError):
            AqualinkAuthState.from_dict({"username": "foo"})

    def test_auth_state_to_dict_round_trip(self) -> None:
        auth_state = AqualinkAuthState(
            username="restored-user",
            client_id="restored-session-id",
            authentication_token="restored-token",
            user_id="restored-id",
            id_token="restored-id-token",
            refresh_token="restored-refresh-token",
        )

        assert AqualinkAuthState.from_dict(auth_state.to_dict()) == auth_state

    async def test_auth_state_setter(self) -> None:
        auth_state = AqualinkAuthState(
            username="restored-user",
            client_id="restored-session-id",
            authentication_token="restored-token",
            user_id="restored-id",
            id_token="restored-id-token",
            refresh_token="restored-refresh-token",
        )
        self.client.auth_state = auth_state

        assert self.client.logged is True
        assert self.client.auth_state == auth_state

    async def test_auth_state_setter_clears_client(self) -> None:
        self.client.auth_state = AqualinkAuthState(
            username="restored-user",
            client_id="restored-session-id",
            authentication_token="restored-token",
            user_id="restored-id",
            id_token="restored-id-token",
            refresh_token="restored-refresh-token",
        )

        self.client.auth_state = None

        assert self.client.logged is False
        assert self.client.auth_state is None

    async def test_context_manager_skips_login_when_auth_restored(self) -> None:
        self.client.auth_state = AqualinkAuthState(
            username="restored-user",
            client_id="restored-session-id",
            authentication_token="restored-token",
            user_id="restored-id",
            id_token="restored-id-token",
            refresh_token="restored-refresh-token",
        )

        with patch.object(self.client, "login") as mock_login:
            async with self.client:
                pass

        mock_login.assert_not_called()

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
        mock_request.return_value.text = json.dumps(LOGIN_DATA)

        assert self.client.logged is False

        await self.client.login()

        assert self.client.logged is True

    @patch("httpx.AsyncClient.request")
    async def test_send_request_uses_default_timeout(
        self, mock_request
    ) -> None:
        mock_request.return_value.status_code = 200

        await self.client.send_request("https://example.com")

        assert (
            mock_request.call_args.kwargs["timeout"] == DEFAULT_REQUEST_TIMEOUT
        )

    @patch("httpx.AsyncClient.request")
    async def test_send_request_preserves_explicit_timeout(
        self, mock_request
    ) -> None:
        mock_request.return_value.status_code = 200

        await self.client.send_request("https://example.com", timeout=3.0)

        assert mock_request.call_args.kwargs["timeout"] == 3.0

    @patch("httpx.AsyncClient.request")
    async def test_login_failed(self, mock_request) -> None:
        mock_request.return_value.status_code = 401

        assert self.client.logged is False

        with pytest.raises(AqualinkServiceException):
            await self.client.login()

        assert self.client.logged is False

    @patch("httpx.AsyncClient.request")
    async def test_login_does_not_retry_unauthorized(
        self, mock_request
    ) -> None:
        mock_request.return_value.status_code = 401

        with (
            pytest.raises(AqualinkServiceException),
            patch.object(self.client, "_refresh_auth") as mock_refresh,
        ):
            await self.client.login()

        mock_refresh.assert_not_called()
        assert mock_request.call_count == 1

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
        mock_request.return_value.text = json.dumps(LOGIN_DATA)

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
        mock_request.return_value.text = json.dumps(LOGIN_DATA)

        await self.client.login()

        systems_data = [{"device_type": "foo", "serial_number": "SN123456"}]
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = systems_data
        mock_request.return_value.text = json.dumps(systems_data)

        systems = await self.client.get_systems()
        assert len(systems) == 1
        assert isinstance(next(iter(systems.values())), UnsupportedSystem)

    @patch("httpx.AsyncClient.request")
    async def test_systems_request(self, mock_request) -> None:
        mock_request.return_value.status_code = 200
        mock_request.return_value.json = MagicMock(return_value=LOGIN_DATA)
        mock_request.return_value.text = json.dumps(LOGIN_DATA)

        await self.client.login()

        systems_data = [{"device_type": "iaqua", "serial_number": "SN123456"}]
        mock_request.return_value.status_code = 200
        mock_request.return_value.json.return_value = systems_data
        mock_request.return_value.text = json.dumps(systems_data)

        systems = await self.client.get_systems()
        assert len(systems) == 1

    @patch("httpx.AsyncClient.request")
    async def test_systems_request_retries_after_refresh(
        self, mock_request
    ) -> None:
        mock_request.side_effect = [
            _make_resp(200, LOGIN_DATA_WITH_REFRESH),
            _make_resp(401),
            _make_resp(200, REFRESH_RESPONSE_DATA),
            _make_resp(200, []),
        ]

        await self.client.login()
        systems = await self.client.get_systems()

        assert systems == {}
        retry_url = mock_request.call_args_list[3][0][1]
        assert "authentication_token=new-token" in retry_url
        assert "user_id=1" in retry_url

    @patch("httpx.AsyncClient.request")
    async def test_systems_request_repeated_401_refreshes_only_once(
        self, mock_request
    ) -> None:
        mock_request.side_effect = [
            _make_resp(401),
            _make_resp(401),
        ]
        self.client._logged = True
        self.client.refresh_token = "refresh-token"

        with (
            patch.object(
                self.client, "_refresh_auth", return_value=None
            ) as mock_refresh,
            pytest.raises(AqualinkServiceUnauthorizedException),
        ):
            await self.client._send_systems_request()

        mock_refresh.assert_awaited_once()

    @patch("httpx.AsyncClient.request")
    async def test_systems_request_404_maps_to_unauthorized(
        self, mock_request
    ) -> None:
        mock_request.return_value.status_code = 404

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await self.client.get_systems()

    @respx.mock
    async def test_429_raises_throttled_immediately(self) -> None:
        respx.get("https://example.com").mock(
            return_value=httpx.Response(
                status_code=httpx.codes.TOO_MANY_REQUESTS
            )
        )

        with pytest.raises(AqualinkServiceThrottledException):
            await self.client.send_request("https://example.com")

    @patch("httpx.AsyncClient.request")
    async def test_500_not_retried(self, mock_request) -> None:
        mock_request.return_value.status_code = (
            httpx.codes.INTERNAL_SERVER_ERROR
        )
        mock_request.return_value.reason_phrase = "Internal Server Error"

        with pytest.raises(AqualinkServiceException):
            await self.client.send_request("https://example.com")

        assert mock_request.call_count == 1

    @patch("httpx.AsyncClient.request")
    async def test_401_not_retried(self, mock_request) -> None:
        mock_request.return_value.status_code = httpx.codes.UNAUTHORIZED

        with pytest.raises(AqualinkServiceUnauthorizedException):
            await self.client.send_request("https://example.com")

        assert mock_request.call_count == 1

    async def test_refresh_auth_concurrent_calls_only_refresh_once(
        self,
    ) -> None:
        self.client.refresh_token = "refresh-token"
        self.client._logged = False

        started = asyncio.Event()
        release = asyncio.Event()

        async def fake_send_refresh_request() -> MagicMock:
            started.set()
            await release.wait()
            return _make_resp(200, REFRESH_RESPONSE_DATA)

        with patch.object(
            self.client,
            "_send_refresh_request",
            side_effect=fake_send_refresh_request,
        ) as mock_refresh:
            first = asyncio.create_task(self.client._refresh_auth())
            await started.wait()
            second = asyncio.create_task(self.client._refresh_auth())

            release.set()
            await asyncio.gather(first, second)

        mock_refresh.assert_awaited_once()
        assert self.client.logged is True
        assert (
            self.client.authentication_token
            == REFRESH_RESPONSE_DATA["authentication_token"]
        )

    @patch("httpx.AsyncClient.request")
    async def test_refresh_request_does_not_retry_unauthorized(
        self, mock_request
    ) -> None:
        mock_request.return_value.status_code = 401
        self.client.refresh_token = "refresh-token"

        with (
            pytest.raises(AqualinkServiceUnauthorizedException),
            patch.object(self.client, "login") as mock_login,
        ):
            await self.client._send_refresh_request()

        mock_login.assert_not_called()
        assert mock_request.call_count == 1

    @patch("httpx.AsyncClient.request")
    async def test_refresh_throttled_propagates_from_send_request(
        self, mock_request
    ) -> None:
        mock_request.side_effect = [
            _make_resp(200, LOGIN_DATA_WITH_REFRESH),
            _make_resp(401),
        ]

        await self.client.login()
        with (
            patch.object(
                self.client,
                "_refresh_auth",
                side_effect=AqualinkServiceThrottledException("Rate limited"),
            ),
            pytest.raises(AqualinkServiceThrottledException),
        ):
            await self.client._send_systems_request()

    @patch("httpx.AsyncClient.request")
    async def test_401_without_refresh_token_falls_back_to_login(
        self, mock_request
    ) -> None:
        mock_request.side_effect = [
            _make_resp(200, LOGIN_DATA),  # login — no RefreshToken in response
            _make_resp(401),
            _make_resp(200, LOGIN_DATA),
            _make_resp(200, []),
        ]

        await self.client.login()
        response = await self.client._send_systems_request()

        assert response.status_code == httpx.codes.OK
        assert mock_request.call_count == 4

    @patch("httpx.AsyncClient.request")
    async def test_systems_request_500_after_refresh_raises_service_exception(
        self, mock_request
    ) -> None:
        mock_request.side_effect = [
            _make_resp(401),
            _make_resp(500),
        ]

        with (
            patch.object(self.client, "_refresh_auth", return_value=None),
            pytest.raises(AqualinkServiceException) as exc_info,
        ):
            await self.client._send_systems_request()

        assert not isinstance(
            exc_info.value, AqualinkServiceUnauthorizedException
        )

    @patch("httpx.AsyncClient.request")
    async def test_refresh_retains_existing_token_when_none_returned(
        self, mock_request
    ) -> None:
        # If the refresh response omits RefreshToken, keep the existing one.
        refresh_no_new_token = {
            "id": 1,
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
        original_refresh_token = self.client.refresh_token
        await self.client._send_systems_request()

        assert self.client.refresh_token == original_refresh_token
