from __future__ import annotations

import logging
from types import TracebackType
from typing import Any, Dict, Optional, Type

import httpx

from iaqualink.const import (
    AQUALINK_API_KEY,
    AQUALINK_DEVICES_URL,
    AQUALINK_LOGIN_URL,
    KEEPALIVE_EXPIRY,
)
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
    AqualinkSystemUnsupportedException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems import *  # noqa: F401,F403

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
        httpx_client: Optional[httpx.AsyncClient] = None,
    ):
        self._username = username
        self._password = password
        self._logged = False

        self._client: Optional[httpx.AsyncClient] = None

        if httpx_client is None:
            self._client = None
            self._must_close_client = True
        else:
            self._client = httpx_client
            self._must_close_client = False

        self.client_id = ""
        self._token = ""
        self._user_id = ""

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

    async def __aenter__(self) -> AqualinkClient:
        try:
            await self.login()
            return self
        except AqualinkServiceException:
            await self.close()
            raise

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc: Optional[BaseException],
        tb: Optional[TracebackType],
    ) -> Optional[bool]:
        # All Exceptions get re-raised.
        await self.close()
        return exc is None

    async def send_request(
        self, url: str, method: str = "get", **kwargs: Any
    ) -> httpx.Response:
        if self._client is None:
            self._client = httpx.AsyncClient(
                http2=True,
                limits=httpx.Limits(keepalive_expiry=KEEPALIVE_EXPIRY),
            )

        LOGGER.debug(f"-> {method.upper()} {url} {kwargs}")
        r = await self._client.request(
            method, url, headers=AQUALINK_HTTP_HEADERS, **kwargs
        )

        LOGGER.debug(f"<- {r.status_code} {r.reason_phrase} - {url}")

        if r.status_code == 401:
            m = "Unauthorized Access, check your credentials and try again"
            self._logged = False
            raise AqualinkServiceUnauthorizedException

        if r.status_code != 200:
            m = f"Unexpected response: {r.status_code} {r.reason_phrase}"
            raise AqualinkServiceException(m)

        return r

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

    async def get_systems(self) -> Dict[str, AqualinkSystem]:
        try:
            r = await self._send_systems_request()
        except AqualinkServiceException as e:
            if "404" in str(e):
                raise AqualinkServiceUnauthorizedException from e
            raise

        data = r.json()

        systems = []
        for x in data:
            try:
                systems += [AqualinkSystem.from_data(self, x)]
            except AqualinkSystemUnsupportedException:
                pass

        return {x.serial: x for x in systems if x is not None}
