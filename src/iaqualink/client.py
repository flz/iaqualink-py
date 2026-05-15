from __future__ import annotations

import asyncio
import importlib
import logging
import time
from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any, Self

import httpx

from iaqualink.const import (
    AQUALINK_API_KEY,
    AQUALINK_API_SIGNING_KEY,
    AQUALINK_DEVICES_URL,
    AQUALINK_LOGIN_URL,
    AQUALINK_REFRESH_URL,
    DEFAULT_REQUEST_TIMEOUT,
    KEEPALIVE_EXPIRY,
)
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
)
from iaqualink.reauth import send_with_reauth_retry
from iaqualink.util import sign
from iaqualink.system import AqualinkSystem

if TYPE_CHECKING:
    from types import TracebackType

for module_name in (
    "iaqualink.systems.exo.system",
    "iaqualink.systems.i2d.system",
    "iaqualink.systems.iaqua.system",
):
    importlib.import_module(module_name)

AQUALINK_HTTP_HEADERS = {
    "user-agent": "okhttp/3.14.7",
    "content-type": "application/json",
}

LOGGER = logging.getLogger("iaqualink")


@dataclass(frozen=True)
class AqualinkAuthState:
    username: str
    client_id: str
    authentication_token: str
    user_id: str
    id_token: str
    refresh_token: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        required_fields = (
            "username",
            "client_id",
            "authentication_token",
            "user_id",
            "id_token",
            "refresh_token",
        )
        values: dict[str, str] = {}
        for field_name in required_fields:
            value = data.get(field_name)
            if not isinstance(value, str) or not value:
                raise ValueError(
                    f"Missing or invalid auth state field: {field_name}"
                )
            values[field_name] = value

        return cls(**values)


class AqualinkClient:
    def __init__(
        self,
        username: str,
        password: str,
        httpx_client: httpx.AsyncClient | None = None,
    ):
        self.username = username
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
        self.authentication_token = ""
        self.user_id = ""
        self.id_token = ""
        self.refresh_token = ""
        self.country = ""
        self._refresh_lock = asyncio.Lock()

        self._last_refresh = 0

    @property
    def logged(self) -> bool:
        return self._logged

    @property
    def auth_state(self) -> AqualinkAuthState | None:
        if not self._logged:
            return None

        return AqualinkAuthState(
            username=self.username,
            client_id=self.client_id,
            authentication_token=self.authentication_token,
            user_id=self.user_id,
            id_token=self.id_token,
            refresh_token=self.refresh_token,
        )

    @auth_state.setter
    def auth_state(self, state: AqualinkAuthState | None) -> None:
        if state is None:
            self._clear_auth_state()
            return

        self.username = state.username
        self.client_id = state.client_id
        self.authentication_token = state.authentication_token
        self.user_id = state.user_id
        self.id_token = state.id_token
        self.refresh_token = state.refresh_token
        self._logged = True

    async def close(self) -> None:
        if self._must_close_client is False:
            return

        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> Self:
        try:
            if not self._logged:
                await self.login()
            else:
                # Auth was restored from a persisted session; force a refresh to
                # obtain fresh tokens and populate attributes (e.g. country) that
                # are not stored in the session.
                self._logged = False
                await self._refresh_auth()
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
        client = self._get_httpx_client()

        headers = AQUALINK_HTTP_HEADERS.copy()
        headers.update(kwargs.pop("headers", {}))
        kwargs.setdefault("timeout", DEFAULT_REQUEST_TIMEOUT)

        LOGGER.debug("-> %s %s %s", method.upper(), url, kwargs)
        try:
            r = await client.request(method, url, headers=headers, **kwargs)
        except (httpx.TransportError, OSError) as e:
            # TransportError covers all Timeout* and Connect*/Read*/WriteError variants;
            # OSError covers platform-level socket errors (e.g. "network unreachable").
            raise AqualinkServiceException(
                f"Request failed: {method.upper()} {url}: {e}"
            ) from e

        LOGGER.debug("<- %s %s - %s", r.status_code, r.reason_phrase, url)

        if r.status_code == httpx.codes.UNAUTHORIZED:
            self._logged = False
            raise AqualinkServiceUnauthorizedException()

        if r.status_code == httpx.codes.TOO_MANY_REQUESTS:
            LOGGER.warning("Rate limited (429)")
            raise AqualinkServiceThrottledException("Rate limited")

        if r.status_code != httpx.codes.OK:
            LOGGER.debug("<- body: %s", r.text)
            m = f"Unexpected response: {r.status_code} {r.reason_phrase}"
            raise AqualinkServiceException(m, response=r)

        return r

    def _get_httpx_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                http2=True,
                limits=httpx.Limits(keepalive_expiry=KEEPALIVE_EXPIRY),
            )
        return self._client

    async def _send_login_request(self) -> httpx.Response:
        data = {
            "api_key": AQUALINK_API_KEY,
            "email": self.username,
            "password": self._password,
        }
        return await self.send_request(
            AQUALINK_LOGIN_URL, method="post", json=data
        )

    async def _send_refresh_request(self) -> httpx.Response:
        # api_key is intentionally omitted — the refresh endpoint does not
        # require it (unlike the login endpoint).
        data = {
            "email": self.username,
            "refresh_token": self.refresh_token,
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

            if not self.refresh_token:
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
                refresh_token_fallback=self.refresh_token,
            )

    async def login(self) -> None:
        r = await self._send_login_request()
        self._apply_login_data(r.json(), refresh_token_fallback="")

    def _clear_auth_state(self) -> None:
        self.client_id = ""
        self.authentication_token = ""
        self.user_id = ""
        self.id_token = ""
        self.refresh_token = ""
        self.country = ""
        self._logged = False

    def _apply_login_data(
        self,
        data: dict[str, Any],
        refresh_token_fallback: str,
    ) -> None:
        self.client_id = data["session_id"]
        self.authentication_token = data["authentication_token"]
        self.user_id = str(data["id"])
        self.id_token = data["userPoolOAuth"]["IdToken"]
        if not self.id_token:
            raise AqualinkServiceException("Login response missing IdToken")
        self.refresh_token = data["userPoolOAuth"].get(
            "RefreshToken", refresh_token_fallback
        )
        self.country = (data.get("country") or "us").lower()
        self._logged = True

    async def _send_systems_request(self) -> httpx.Response:
        async def do_request() -> httpx.Response:
            timestamp = str(int(time.time()))
            signature = sign(
                [self.user_id, timestamp], AQUALINK_API_SIGNING_KEY
            )
            return await self.send_request(
                AQUALINK_DEVICES_URL,
                params={
                    "user_id": self.user_id,
                    "signature": signature,
                    "timestamp": timestamp,
                },
                headers={
                    "api_key": AQUALINK_API_KEY,
                    "Authorization": f"Bearer {self.id_token}",
                },
            )

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
        LOGGER.debug("Systems response: %s", data)

        systems = [AqualinkSystem.from_data(self, x) for x in data]
        return {x.serial: x for x in systems}
