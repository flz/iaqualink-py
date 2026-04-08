from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import TYPE_CHECKING, Any, Self

import httpx

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
from iaqualink.system import AqualinkSystem
from iaqualink.systems import *  # noqa: F403

if TYPE_CHECKING:
    from types import TracebackType

AQUALINK_HTTP_HEADERS = {
    "user-agent": "okhttp/3.14.7",
    "content-type": "application/json",
}

LOGGER = logging.getLogger("iaqualink")


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

        self._last_refresh = 0

    @property
    def logged(self) -> bool:
        return self._logged

    async def close(self) -> None:
        if self._must_close_client is False:
            return

        # There shouldn't be a case where this is None but this quietens mypy.
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
        retry: bool = True,
        **kwargs: Any,
    ) -> httpx.Response:
        """Send an HTTP request with optional retry on 429 responses.

        By default (``retry=True``) every request, including login,
        retries up to :data:`RETRY_MAX_ATTEMPTS` times on 429.
        Server-provided ``Retry-After`` values are honoured up to
        :data:`RETRY_AFTER_MAX_DELAY` (60 s); callers that need
        tighter latency should catch
        :exc:`AqualinkServiceThrottledException` or wrap calls with
        :func:`asyncio.wait_for`.

        When ``retry=False`` (``max_attempts=1``) the single attempt
        raises :exc:`AqualinkServiceThrottledException` immediately on
        429 with no actual retry.
        """
        if self._client is None:
            self._client = httpx.AsyncClient(
                http2=True,
                limits=httpx.Limits(keepalive_expiry=KEEPALIVE_EXPIRY),
            )

        headers = AQUALINK_HTTP_HEADERS.copy()
        headers.update(kwargs.pop("headers", {}))

        max_attempts = RETRY_MAX_ATTEMPTS if retry else 1

        attempt_429 = 0
        refreshed = False

        while True:
            LOGGER.debug("-> %s %s %s", method.upper(), url, kwargs)
            r = await self._client.request(
                method, url, headers=headers, **kwargs
            )

            LOGGER.debug("<- %s %s - %s", r.status_code, r.reason_phrase, url)

            if r.status_code == httpx.codes.UNAUTHORIZED:
                was_logged = self._logged
                self._logged = False
                if was_logged and self._refresh_token and not refreshed:
                    refreshed = True
                    await self._refresh_auth()
                    # _refresh_auth sets _logged=True, but the Authorization
                    # header below hasn't been updated yet. The window is
                    # narrow (no await between here and continue) so a
                    # concurrent coroutine that reads _logged=True would still
                    # use its own locally-built headers — not ours.
                    if "Authorization" in headers:
                        old = headers["Authorization"]
                        # Preserve caller format: "Bearer <token>" (iAqua) or
                        # raw token (eXO). Case-sensitive match is intentional
                        # — `headers` is a plain dict whose keys are set by
                        # this method and by callers, all using title-case.
                        # Converting to httpx.Headers just for this check
                        # would be over-engineered.
                        prefix = "Bearer " if old.startswith("Bearer ") else ""
                        headers["Authorization"] = f"{prefix}{self.id_token}"
                    # Reset the 429 counter so the post-refresh retry gets
                    # its own full rate-limit budget; 429s before the token
                    # expired should not penalise the refreshed request.
                    attempt_429 = 0
                    # Re-enter the loop so 429 backoff applies to the retry.
                    continue
                raise AqualinkServiceUnauthorizedException()

            if r.status_code == httpx.codes.TOO_MANY_REQUESTS:
                LOGGER.debug("429 response headers: %s", dict(r.headers))
                if attempt_429 < max_attempts - 1:
                    delay = self._get_retry_delay(r, attempt_429)
                    LOGGER.warning(
                        "Rate limited (429), retry %d/%d in %.1fs",
                        attempt_429 + 1,
                        max_attempts,
                        delay,
                    )
                    await asyncio.sleep(delay)
                    attempt_429 += 1
                    continue
                break

            if r.status_code != httpx.codes.OK:
                m = f"Unexpected response: {r.status_code} {r.reason_phrase}"
                raise AqualinkServiceException(m)

            return r

        LOGGER.warning(
            "Rate limited (429), giving up after %d attempt(s)",
            max_attempts,
        )
        raise AqualinkServiceThrottledException(
            f"Rate limited after {max_attempts} attempt(s)"
        )

    @staticmethod
    def _get_retry_delay(response: httpx.Response, attempt: int) -> float:
        """Determine delay before the next retry.

        Fallback order: numeric Retry-After → HTTP-date Retry-After
        → exponential backoff with half-jitter.
        """
        retry_after = response.headers.get("retry-after")
        if retry_after is not None:
            try:
                return min(float(retry_after), RETRY_AFTER_MAX_DELAY)
            except ValueError:
                pass

            try:
                dt = parsedate_to_datetime(retry_after)
                delay = (dt - datetime.now(tz=timezone.utc)).total_seconds()
                if delay > 0:
                    return min(delay, RETRY_AFTER_MAX_DELAY)
            except (ValueError, TypeError):
                pass

            LOGGER.debug(
                "Could not parse Retry-After header: %s",
                retry_after,
            )

        delay = min(RETRY_BASE_DELAY * (2**attempt), RETRY_MAX_DELAY)
        return random.uniform(delay / 2, delay)

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

        Called from :meth:`send_request` when a 401 is received and a
        refresh token is available.  Re-entrancy is prevented because
        :attr:`_logged` is ``False`` by the time this method is called,
        so the inner call to :meth:`send_request` skips the refresh path.

        Only :exc:`AqualinkServiceUnauthorizedException` (401) from the
        refresh endpoint is caught — other errors (5xx, throttle) propagate
        to the caller of :meth:`send_request` unchanged.  If the fallback
        :meth:`login` also raises (wrong password, network error, 429),
        that exception likewise propagates from :meth:`send_request` with
        no additional wrapping.
        """
        # _send_refresh_request calls send_request, which would normally
        # attempt another token refresh on 401 — that is prevented because
        # self._logged is False by the time this method is called, so the
        # re-entrant 401 path in send_request is skipped.
        try:
            r = await self._send_refresh_request()
        except AqualinkServiceUnauthorizedException:
            # Refresh token is expired or invalid — fall back to full login.
            await self.login()
            return

        data = r.json()
        self.client_id = data["session_id"]
        self._token = data["authentication_token"]
        self._user_id = data["id"]
        self.id_token = data["userPoolOAuth"]["IdToken"]
        self._refresh_token = data["userPoolOAuth"].get(
            "RefreshToken", self._refresh_token
        )
        self._logged = True

    async def login(self) -> None:
        r = await self._send_login_request()

        data = r.json()
        self.client_id = data["session_id"]
        self._token = data["authentication_token"]
        self._iot_credentials = data.get("credentials", None)
        self._user_id = data["id"]
        self.id_token = data["userPoolOAuth"]["IdToken"]
        self._refresh_token = data["userPoolOAuth"].get("RefreshToken", "")
        self._logged = True

    async def _send_systems_request(self) -> httpx.Response:
        params = {
            "api_key": AQUALINK_API_KEY,
            "authentication_token": self._token,
            "user_id": self._user_id,
        }
        params_str = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{AQUALINK_DEVICES_URL}?{params_str}"
        return await self.send_request(url)

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
