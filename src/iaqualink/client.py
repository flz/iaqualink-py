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
    AqualinkLoginException,
    AqualinkServiceException,
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
        self.username = username
        self.password = password

        if session is None:
            self.session = aiohttp.ClientSession()
            self._must_clean_session = True
        else:
            self.session = session
            self._must_clean_session = False

        self.session_id = None
        self.token = None
        self.user_id = None

        self.lock = threading.Lock()
        self.last_refresh = 0

    async def _cleanup_session(self):
        if self._must_clean_session is True:
            await self.session.close()

    async def __aenter__(self):
        try:
            await self.login()
            return self
        except AqualinkLoginException:
            await self._cleanup_session()
            raise

    async def __aexit__(self, exc_type, exc, tb):
        # All Exceptions get re-raised.
        await self._cleanup_session()
        return exc is None

    async def _send_request(
        self, url: str, method: str = "get", **kwargs
    ) -> aiohttp.ClientResponse:
        LOGGER.debug(f"-> {method.upper()} {url} {kwargs}")
        r = await self.session.request(
            method, url, headers=AQUALINK_HTTP_HEADERS, **kwargs
        )

        LOGGER.debug(f"<- {r.status} {r.reason} - {url}")
        if r.status != 200:
            m = f"Unexpected response: {r.status} {r.reason}"
            raise AqualinkServiceException(m)
        return r

    async def _send_login_request(self) -> aiohttp.ClientResponse:
        data = {
            "api_key": AQUALINK_API_KEY,
            "email": self.username,
            "password": self.password,
        }
        return await self._send_request(
            AQUALINK_LOGIN_URL, method="post", json=data
        )

    async def login(self) -> None:
        try:
            r = await self._send_login_request()
        except AqualinkServiceException as e:
            m = "Failed to login"
            raise AqualinkLoginException(m) from e

        data = await r.json()
        self.session_id = data["session_id"]
        self.token = data["authentication_token"]
        self.user_id = data["id"]

    async def _send_systems_request(self) -> aiohttp.ClientResponse:
        params = {
            "api_key": AQUALINK_API_KEY,
            "authentication_token": self.token,
            "user_id": self.user_id,
        }
        params = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{AQUALINK_DEVICES_URL}?{params}"
        return await self._send_request(url)

    async def get_systems(self) -> typing.Dict[str, AqualinkSystem]:
        r = await self._send_systems_request()

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
                "sessionID": self.session_id,
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
