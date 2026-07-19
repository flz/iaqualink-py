from __future__ import annotations

__all__ = ["AqualinkAuthState", "AqualinkClient"]

import asyncio
import importlib
import json
import logging
import time
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass
from dataclasses import fields as dataclass_fields
from typing import TYPE_CHECKING, Any, Self
from urllib.parse import urlsplit

import httpx
from httpx_ws import (
    WebSocketDisconnect,
    WebSocketInvalidTypeReceived,
    WebSocketUpgradeError,
    aconnect_ws,
)

from iaqualink.const import (
    AQUALINK_API_KEY,
    AQUALINK_API_SIGNING_KEY,
    AQUALINK_DEVICES_URL,
    AQUALINK_LOGIN_URL,
    AQUALINK_REFRESH_URL,
    DEFAULT_REQUEST_TIMEOUT,
    KEEPALIVE_EXPIRY,
    WS_ACK_TIMEOUT,
)
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceThrottledException,
    AqualinkServiceUnauthorizedException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.utils.crypto import sign
from iaqualink.utils.reauth import send_with_reauth_retry
from iaqualink.utils.redact import (
    REDACT_KEYS,
    mask_email,
    mask_serial,
    redact_kwargs,
    redact_url,
    redact_value,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from types import TracebackType

    from httpx_ws import AsyncWebSocketSession

for module_name in (
    "iaqualink.systems.cyclobat.system",
    "iaqualink.systems.exo.system",
    "iaqualink.systems.i2d.system",
    "iaqualink.systems.iaqua.system",
    "iaqualink.systems.vr.system",
    "iaqualink.systems.vortrax.system",
):
    importlib.import_module(module_name)

AQUALINK_HTTP_HEADERS = {
    "user-agent": "okhttp/3.14.7",
    "content-type": "application/json",
}

LOGGER = logging.getLogger("iaqualink.client")


@dataclass(frozen=True)
class AqualinkAuthState:
    username: str
    client_id: str
    authentication_token: str
    user_id: str
    id_token: str
    refresh_token: str
    app_client_id: str = ""

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

        app_client_id = data.get("app_client_id", "")
        if not isinstance(app_client_id, str):
            app_client_id = ""
        return cls(app_client_id=app_client_id, **values)

    def __repr__(self) -> str:
        parts = ", ".join(
            f"{f.name}={mask_email(getattr(self, f.name))}"
            if f.name == "username"
            else f"{f.name}=***"
            if f.name in REDACT_KEYS
            else f"{f.name}={getattr(self, f.name)!r}"
            for f in dataclass_fields(self)
        )
        return f"AqualinkAuthState({parts})"


class AqualinkClient:
    def __init__(
        self,
        username: str,
        password: str,
        httpx_client: httpx.AsyncClient | None = None,
        event_hooks: dict[str, list] | None = None,
    ):
        self.username = username
        self._password = password
        self._logged = False

        self._event_hooks: dict[str, list] = event_hooks or {}
        self._client: httpx.AsyncClient | None = None
        # Dedicated HTTP/1.1 client for WebSockets (see _get_ws_httpx_client).
        self._ws_client: httpx.AsyncClient | None = None

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
        self.app_client_id = ""
        self.country = ""
        self._refresh_lock = asyncio.Lock()

        self._last_refresh = 0
        # Populated after get_systems() returns. Requests made before that point
        # (login, device-list) will contain unmasked serials in debug-log URLs.
        self._log_serials: set[str] = set()

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
            app_client_id=self.app_client_id,
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
        self.app_client_id = state.app_client_id
        self._logged = True

    async def close(self) -> None:
        # The WS client is always ours (never HA-injected), so always close it.
        if self._ws_client is not None:
            await self._ws_client.aclose()
            self._ws_client = None

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

    def _log_redact_url(self, url: str) -> str:
        url = redact_url(url)
        for serial in self._log_serials:
            url = url.replace(serial, mask_serial(serial))
        return url

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

        LOGGER.debug(
            "-> %s %s %s",
            method.upper(),
            self._log_redact_url(url),
            redact_kwargs(kwargs),
        )
        try:
            r = await client.request(method, url, headers=headers, **kwargs)
        except (httpx.TransportError, OSError) as e:
            # TransportError covers all Timeout* and Connect*/Read*/WriteError variants;
            # OSError covers platform-level socket errors (e.g. "network unreachable").
            raise AqualinkServiceException(
                f"Request failed: {method.upper()} {url}: {e}"
            ) from e

        LOGGER.debug(
            "<- %s %s - %s",
            r.status_code,
            r.reason_phrase,
            self._log_redact_url(url),
        )

        if r.status_code == httpx.codes.UNAUTHORIZED:
            self._logged = False
            raise AqualinkServiceUnauthorizedException()

        if r.status_code == httpx.codes.TOO_MANY_REQUESTS:
            LOGGER.warning("Rate limited (429)")
            raise AqualinkServiceThrottledException("Rate limited")

        if r.status_code != httpx.codes.OK:
            try:
                _err_body = redact_value(json.loads(r.text))
            except (json.JSONDecodeError, TypeError):  # fmt: skip
                _err_body = r.text
            LOGGER.debug("<- body: %s", _err_body)
            m = f"Unexpected response: {r.status_code} {r.reason_phrase}"
            raise AqualinkServiceException(m, response=r)

        return r

    def _get_httpx_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                http2=True,
                limits=httpx.Limits(keepalive_expiry=KEEPALIVE_EXPIRY),
                event_hooks=self._event_hooks,
            )
        return self._client

    def _get_ws_httpx_client(self) -> httpx.AsyncClient:
        # WebSockets ride a dedicated HTTP/1.1 client: the upgrade is an
        # HTTP/1.1 mechanism (`Connection: Upgrade`), invalid over the REST
        # client's HTTP/2 — the endpoint rejects it with 400. Separate from the
        # (possibly HA-injected, HTTP/2) REST client; carries no REST cookies.
        if self._ws_client is None:
            self._ws_client = httpx.AsyncClient(
                http1=True,
                http2=False,
                limits=httpx.Limits(keepalive_expiry=KEEPALIVE_EXPIRY),
            )
        return self._ws_client

    @asynccontextmanager
    async def ws_connect(
        self,
        url: str,
        *,
        keepalive_ping_interval_seconds: float | None = None,
    ) -> AsyncIterator[AsyncWebSocketSession]:
        """Open an authenticated WebSocket over the dedicated HTTP/1.1 client.

        Reused by robot commands and state subscriptions (and other wss-based
        systems such as tcx). ``keepalive_ping_interval_seconds`` enables
        periodic WS pings so a silently dropped connection raises instead of
        blocking forever — set it for long-lived subscriptions; None for
        one-shot sends.
        """
        parts = urlsplit(url)
        headers = {
            "Authorization": self.id_token,
            # Match the vendor app handshake (the WAF in front of the endpoint
            # expects an Origin matching the host).
            "Origin": f"{parts.scheme}://{parts.netloc}",
        }
        kwargs: dict[str, Any] = {}
        if keepalive_ping_interval_seconds is not None:
            kwargs["keepalive_ping_interval_seconds"] = (
                keepalive_ping_interval_seconds
            )
        try:
            async with aconnect_ws(
                url, self._get_ws_httpx_client(), headers=headers, **kwargs
            ) as ws:
                yield ws
        except WebSocketUpgradeError as exc:
            # A 401/403 on the WS handshake means the bearer token is stale,
            # same as the REST path — surface it as unauthorized so callers can
            # reauth and retry. Other upgrade failures propagate unchanged.
            if exc.response.status_code in (401, 403):
                raise AqualinkServiceUnauthorizedException from exc
            raise

    async def send_ws_frame(
        self,
        url: str,
        frame: dict[str, Any],
        *,
        ack_timeout: float = WS_ACK_TIMEOUT,
    ) -> None:
        """Open a one-shot WS, send `frame` as JSON, best-effort wait for ack."""
        LOGGER.debug(
            "-> WS %s action=%s",
            self._log_redact_url(url),
            frame.get("action"),
        )

        async def do_send() -> None:
            async with self.ws_connect(url) as ws:
                await ws.send_text(json.dumps(frame))
                try:
                    ack = await ws.receive_text(timeout=ack_timeout)
                except (
                    TimeoutError,
                    WebSocketDisconnect,
                    WebSocketInvalidTypeReceived,
                ) as exc:
                    LOGGER.debug("No WS ack within %.1fs: %r", ack_timeout, exc)
                else:
                    LOGGER.debug("WS ack received (length=%d)", len(ack))

        # Mirror the REST read path: reauth once on a stale-token handshake.
        await send_with_reauth_retry(do_send, self._refresh_auth)

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
                LOGGER.info(
                    "Refresh token expired, re-authenticating: user=%s",
                    mask_email(self.username),
                )
                await self.login()
                return

            self._apply_login_data(
                r.json(),
                refresh_token_fallback=self.refresh_token,
            )
            LOGGER.info(
                "Auth token refreshed: user=%s", mask_email(self.username)
            )

    async def login(self) -> None:
        r = await self._send_login_request()
        self._apply_login_data(r.json(), refresh_token_fallback="")
        LOGGER.info("Authenticated: user=%s", mask_email(self.username))

    def _clear_auth_state(self) -> None:
        self.client_id = ""
        self.authentication_token = ""
        self.user_id = ""
        self.id_token = ""
        self.refresh_token = ""
        self.app_client_id = ""
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
        cognito = data.get("cognitoPool") or {}
        self.app_client_id = cognito.get("appClientId", "")
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
        LOGGER.debug("Systems body: %s", redact_value(data))
        LOGGER.debug("get_systems: %d system(s) discovered", len(data))

        systems = [AqualinkSystem.from_data(self, x) for x in data]
        self._log_serials.update(s.serial for s in systems if s.serial)
        return {x.serial: x for x in systems}
