from __future__ import annotations

import logging
import threading
import typing

import aiohttp

from iaqualink.const import (
    AQUALINK_API_KEY,
    AQUALINK_LOGIN_URL,
    AQUALINK_DEVICES_URL,
    AQUALINK_SESSION_URL,
    AQUALINK_COMMAND_GET_HOME,
    AQUALINK_COMMAND_GET_DEVICES,
)
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.typing import Payload


AQUALINK_HTTP_HEADERS = {
    "User-Agent": "iAquaLink/70 CFNetwork/901.1 Darwin/17.6.0",
    "Content-Type": "application/json",
    "Accept": "*/*",
}

LOGGER = logging.getLogger("iaqualink")


class AqualinkClient:
    def __init__(
        self,
        username: str,
        password: str,
        session: typing.Optional[aiohttp.ClientSession] = None,
    ):
        self._username = username
        self._password = password
        self._logged = False

        if session is None:
            self._session = None
            self._must_clean_session = True
        else:
            self._session = session
            self._must_clean_session = False

        self._session_id = ""
        self._token = ""
        self._user_id = ""

        self._last_refresh = 0

    @property
    def logged(self):
        return self._logged

    async def close(self):
        if self._must_clean_session is True and self.closed is False:
            await self._session.close()

    @property
    def closed(self):
        return self._session is None or self._session.closed is True

    async def __aenter__(self):
        try:
            await self.login()
            return self
        except AqualinkServiceException:
            await self.close()
            raise

    async def __aexit__(self, exc_type, exc, tb):
        # All Exceptions get re-raised.
        await self.close()
        return exc is None

    async def _send_request(
        self, url: str, method: str = "get", **kwargs
    ) -> aiohttp.ClientResponse:
        # One-time instantiation if we weren't given a session.
        if self._must_clean_session and self._session is None:
            self._session = aiohttp.ClientSession()

        LOGGER.debug(f"-> {method.upper()} {url} {kwargs}")
        r = await self._session.request(
            method, url, headers=AQUALINK_HTTP_HEADERS, **kwargs
        )

        LOGGER.debug(f"<- {r.status} {r.reason} - {url}")

        if r.status == 401:
            m = "Unauthorized Access, check your credentials and try again"
            self._logged = False
            raise AqualinkServiceUnauthorizedException

        if r.status != 200:
            m = f"Unexpected response: {r.status} {r.reason}"
            raise AqualinkServiceException(m)

        return r

    async def _send_login_request(self) -> aiohttp.ClientResponse:
        data = {
            "api_key": AQUALINK_API_KEY,
            "email": self._username,
            "password": self._password,
        }
        return await self._send_request(
            AQUALINK_LOGIN_URL, method="post", json=data
        )

    async def login(self) -> None:
        r = await self._send_login_request()

        data = await r.json()
        self._session_id = data["session_id"]
        self._token = data["authentication_token"]
        self._user_id = data["id"]
        self._logged = True

    async def _send_systems_request(self) -> aiohttp.ClientResponse:
        params = {
            "api_key": AQUALINK_API_KEY,
            "authentication_token": self._token,
            "user_id": self._user_id,
        }
        params = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{AQUALINK_DEVICES_URL}?{params}"
        return await self._send_request(url)

    async def get_systems(self) -> typing.Dict[str, AqualinkSystem]:
        try:
            r = await self._send_systems_request()
        except AqualinkServiceException as e:
            if "404" in str(e):
                raise AqualinkServiceUnauthorizedException from e
            raise

        data = await r.json()
        systems = [AqualinkSystem.from_data(self, x) for x in data]
        return {x.serial: x for x in systems if x is not None}

    async def _send_session_request(
        self,
        serial: str,
        command: str,
        params: typing.Optional[Payload] = None,
    ) -> aiohttp.ClientResponse:
        if not params:
            params = {}

        params.update(
            {
                "actionID": "command",
                "command": command,
                "serial": serial,
                "sessionID": self._session_id,
            }
        )
        params = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{AQUALINK_SESSION_URL}?{params}"
        return await self._send_request(url)

    async def send_home_screen_request(self, serial) -> aiohttp.ClientResponse:
        r = await self._send_session_request(serial, AQUALINK_COMMAND_GET_HOME)
        return r

    async def send_devices_screen_request(
        self, serial
    ) -> aiohttp.ClientResponse:
        r = await self._send_session_request(
            serial, AQUALINK_COMMAND_GET_DEVICES
        )
        return r
