from __future__ import annotations

import asyncio
import contextlib
import logging
import random
from typing import TYPE_CHECKING, Any, Self

import httpx

from iaqualink.const import (
    AQUALINK_API_KEY,
    AQUALINK_DEVICES_URL,
    AQUALINK_LOGIN_URL,
    KEEPALIVE_EXPIRY,
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
        **kwargs: Any,
    ) -> httpx.Response:
        if self._client is None:
            self._client = httpx.AsyncClient(
                http2=True,
                limits=httpx.Limits(keepalive_expiry=KEEPALIVE_EXPIRY),
            )

        headers = AQUALINK_HTTP_HEADERS.copy()
        headers.update(kwargs.pop("headers", {}))

        for attempt in range(RETRY_MAX_ATTEMPTS):
            LOGGER.debug(f"-> {method.upper()} {url} {kwargs}")
            r = await self._client.request(
                method, url, headers=headers, **kwargs
            )

            LOGGER.debug(f"<- {r.status_code} {r.reason_phrase} - {url}")

            if r.status_code == httpx.codes.UNAUTHORIZED:
                self._logged = False
                raise AqualinkServiceUnauthorizedException

            if r.status_code == httpx.codes.TOO_MANY_REQUESTS:
                LOGGER.debug(f"429 response headers: {dict(r.headers)}")
                if attempt < RETRY_MAX_ATTEMPTS - 1:
                    delay = self._get_retry_delay(r, attempt)
                    LOGGER.warning(
                        f"Rate limited (429), retry {attempt + 1}/"
                        f"{RETRY_MAX_ATTEMPTS} in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                continue

            if r.status_code != httpx.codes.OK:
                m = f"Unexpected response: {r.status_code} {r.reason_phrase}"
                raise AqualinkServiceException(m)

            return r

        raise AqualinkServiceThrottledException(
            f"Rate limited after {RETRY_MAX_ATTEMPTS} retries"
        )

    @staticmethod
    def _get_retry_delay(response: httpx.Response, attempt: int) -> float:
        retry_after = response.headers.get("retry-after")
        if retry_after is not None:
            try:
                return min(float(retry_after), RETRY_MAX_DELAY)
            except ValueError:
                LOGGER.debug(
                    "Could not parse Retry-After header as seconds: %s",
                    retry_after,
                )

        delay = RETRY_BASE_DELAY * (2**attempt) + random.random()
        return min(delay, RETRY_MAX_DELAY)

    async def _send_login_request(self) -> httpx.Response:
        data = {
            "api_key": AQUALINK_API_KEY,
            "email": self._username,
            "password": self._password,
        }
        return await self.send_request(
            AQUALINK_LOGIN_URL, method="post", json=data
        )

    async def login(self) -> None:
        r = await self._send_login_request()

        data = r.json()
        self.client_id = data["session_id"]
        self._token = data["authentication_token"]
        self._user_id = data["id"]
        self.id_token = data["userPoolOAuth"]["IdToken"]
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
