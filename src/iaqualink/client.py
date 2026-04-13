from __future__ import annotations

import asyncio
import contextlib
import importlib
import logging
from typing import TYPE_CHECKING, Any, Self

import httpx
from httpx_retries import Retry, RetryTransport

from iaqualink.const import (
    AQUALINK_API_KEY,
    AQUALINK_DEVICES_URL,
    AQUALINK_LOGIN_URL,
    AQUALINK_REFRESH_URL,
    KEEPALIVE_EXPIRY,
    RETRY_AFTER_MAX_DELAY,
    RETRY_BASE_DELAY,
    RETRY_MAX_ATTEMPTS,
    RETRY_MAX_DELAY,
)
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
    AqualinkSystemUnsupportedException,
)
from iaqualink.reauth import send_with_reauth_retry
from iaqualink.system import AqualinkSystem

if TYPE_CHECKING:
    from types import TracebackType

for module_name in (
    "iaqualink.systems.exo.system",
    "iaqualink.systems.iaqua.system",
):
    importlib.import_module(module_name)

AQUALINK_HTTP_HEADERS = {
    "user-agent": "okhttp/3.14.7",
    "content-type": "application/json",
}
# POST remains retryable here because the transport only retries explicit 429
# responses, where the server asked the client to retry later rather than
# acknowledging the request. That covers auth POSTs plus the eXO desired-state
# update, which replaces a target state instead of appending a side effect.
RETRYABLE_METHODS = frozenset({"GET", "POST"})

LOGGER = logging.getLogger("iaqualink")


class AqualinkRetry(Retry):
    def parse_retry_after(self, retry_after: str) -> float:
        return min(
            max(super().parse_retry_after(retry_after), 0.0),
            RETRY_AFTER_MAX_DELAY,
        )


class AqualinkClient:
    def __init__(
        self,
        username: str,
        password: str,
        httpx_client: httpx.AsyncClient | None = None,
    ):
        self._username = username
        self._password = password
        self._logged = False

        self._client: httpx.AsyncClient | None = None

        if httpx_client is None:
            self._client = None
            self._must_close_client = True
        else:
            self._client = httpx_client
            self._must_close_client = False

        self.client_id = ""
        self._token = ""
        self._user_id = ""
        self.id_token = ""
        self._refresh_token = ""
        self._refresh_lock = asyncio.Lock()

        self._last_refresh = 0

    @property
    def logged(self) -> bool:
        return self._logged

    async def close(self) -> None:
        if self._must_close_client is False:
            return

        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> Self:
        try:
            await self.login()
        except AqualinkServiceException:
            await self.close()
            raise

        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> bool | None:
        # All Exceptions get re-raised.
        await self.close()
        return exc is None

    async def send_request(
        self,
        url: str,
        method: str = "get",
        **kwargs: Any,
    ) -> httpx.Response:
        """Send an HTTP request.

        The managed client uses ``httpx-retries`` to handle HTTP 429
        responses with exponential backoff and ``Retry-After``.
        """
        client = self._get_httpx_client()

        headers = AQUALINK_HTTP_HEADERS.copy()
        headers.update(kwargs.pop("headers", {}))

        LOGGER.debug("-> %s %s %s", method.upper(), url, kwargs)
        r = await client.request(method, url, headers=headers, **kwargs)

        LOGGER.debug("<- %s %s - %s", r.status_code, r.reason_phrase, url)

        if r.status_code == httpx.codes.UNAUTHORIZED:
            self._logged = False
            raise AqualinkServiceUnauthorizedException()

        if r.status_code == httpx.codes.TOO_MANY_REQUESTS:
            # RetryTransport returns the final 429 response once the retry
            # budget is exhausted, so translate it to the library exception here.
            LOGGER.warning(
                "Rate limited (429), giving up after %d attempt(s)",
                RETRY_MAX_ATTEMPTS,
            )
            raise AqualinkServiceThrottledException(
                f"Rate limited after {RETRY_MAX_ATTEMPTS} attempt(s)"
            )

        if r.status_code != httpx.codes.OK:
            m = f"Unexpected response: {r.status_code} {r.reason_phrase}"
            raise AqualinkServiceException(m)

        return r

    def _build_httpx_client(self) -> httpx.AsyncClient:
        kwargs: dict[str, Any] = {
            "http2": True,
            "limits": httpx.Limits(keepalive_expiry=KEEPALIVE_EXPIRY),
            "transport": RetryTransport(
                retry=AqualinkRetry(
                    total=RETRY_MAX_ATTEMPTS - 1,
                    backoff_factor=RETRY_BASE_DELAY,
                    max_backoff_wait=RETRY_MAX_DELAY,
                    allowed_methods=RETRYABLE_METHODS,
                    status_forcelist={httpx.codes.TOO_MANY_REQUESTS},
                )
            ),
        }
        return httpx.AsyncClient(**kwargs)

    def _get_httpx_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = self._build_httpx_client()
        return self._client

    async def _send_login_request(self) -> httpx.Response:
        data = {
            "api_key": AQUALINK_API_KEY,
            "email": self._username,
            "password": self._password,
        }
        return await self.send_request(
            AQUALINK_LOGIN_URL, method="post", json=data
        )

    async def _send_refresh_request(self) -> httpx.Response:
        # api_key is intentionally omitted — the refresh endpoint does not
        # require it (unlike the login endpoint).
        data = {
            "email": self._username,
            "refresh_token": self._refresh_token,
        }
        return await self.send_request(
            AQUALINK_REFRESH_URL, method="post", json=data
        )

    async def _refresh_auth(self) -> None:
        """Attempt a token refresh; fall back to full login on 401.

        Concurrent unauthorized requests share a single refresh/login attempt.
        Once one waiter restores authentication, later waiters return without
        sending an extra refresh request.

        Only :exc:`AqualinkServiceUnauthorizedException` (401) from the
        refresh endpoint is caught — other errors (5xx, throttle) propagate
        unchanged. If the fallback :meth:`login` also raises, that exception
        likewise propagates with no additional wrapping.
        """
        async with self._refresh_lock:
            if self._logged:
                return

            if not self._refresh_token:
                await self.login()
                return

            try:
                r = await self._send_refresh_request()
            except AqualinkServiceUnauthorizedException:
                # Refresh token is expired or invalid — fall back to full login.
                await self.login()
                return

            self._apply_login_data(
                r.json(),
                refresh_token_fallback=self._refresh_token,
            )

    async def login(self) -> None:
        r = await self._send_login_request()
        self._apply_login_data(r.json(), refresh_token_fallback="")

    def _apply_login_data(
        self,
        data: dict[str, Any],
        refresh_token_fallback: str,
    ) -> None:
        self.client_id = data["session_id"]
        self._token = data["authentication_token"]
        self._user_id = data["id"]
        self.id_token = data["userPoolOAuth"]["IdToken"]
        self._refresh_token = data["userPoolOAuth"].get(
            "RefreshToken", refresh_token_fallback
        )
        self._logged = True

    async def _send_systems_request(self) -> httpx.Response:
        async def do_request() -> httpx.Response:
            params = {
                "api_key": AQUALINK_API_KEY,
                "authentication_token": self._token,
                "user_id": self._user_id,
            }
            params_str = "&".join(f"{k}={v}" for k, v in params.items())
            url = f"{AQUALINK_DEVICES_URL}?{params_str}"
            return await self.send_request(url)

        return await send_with_reauth_retry(
            do_request,
            self._refresh_auth,
        )

    async def get_systems(self) -> dict[str, AqualinkSystem]:
        try:
            r = await self._send_systems_request()
        except AqualinkServiceException as e:
            if "404" in str(e):
                raise AqualinkServiceUnauthorizedException from e
            raise

        data = r.json()

        systems = []
        for x in data:
            with contextlib.suppress(AqualinkSystemUnsupportedException):
                systems += [AqualinkSystem.from_data(self, x)]

        return {x.serial: x for x in systems if x is not None}
