import logging
import threading
from typing import Dict, Optional

import aiohttp

from iaqualink.const import (
    AQUALINK_API_KEY,
    AQUALINK_LOGIN_URL,
    AQUALINK_DEVICES_URL,
    AQUALINK_SESSION_URL,
)
from iaqualink.system import AqualinkSystem
from iaqualink.typing import Payload


AQUALINK_COMMAND_GET_DEVICES = "get_devices"
AQUALINK_COMMAND_GET_HOME = "get_home"
AQUALINK_COMMAND_GET_ONETOUCH = "get_onetouch"
AQUALINK_COMMAND_SET_AUX = "set_aux"
AQUALINK_COMMAND_SET_LIGHT = "set_light"
AQUALINK_COMMAND_SET_POOL_HEATER = "set_pool_heater"
AQUALINK_COMMAND_SET_POOL_PUMP = "set_pool_pump"
AQUALINK_COMMAND_SET_SOLAR_HEATER = "set_solar_heater"
AQUALINK_COMMAND_SET_SPA_HEATER = "set_spa_heater"
AQUALINK_COMMAND_SET_SPA_PUMP = "set_spa_pump"
AQUALINK_COMMAND_SET_TEMPS = "set_temps"

AQUALINK_HTTP_HEADERS = {
    "User-Agent": "iAquaLink/70 CFNetwork/901.1 Darwin/17.6.0",
    "Content-Type": "application/json",
    "Accept": "*/*",
}

LOGGER = logging.getLogger("aqualink")


class AqualinkClient(object):
    def __init__(
        self,
        username: str,
        password: str,
        session: Optional[aiohttp.ClientSession] = None,
    ):
        self.username = username
        self.password = password

        if session is None:
            self.session = aiohttp.ClientSession()
            self._must_clean_session = True
        else:
            self.session = session
            self._must_clean_session = True

        self.session_id = None
        self.token = None
        self.user_id = None

        self.lock = threading.Lock()
        self.last_refresh = 0

    async def __aenter__(self):
        await self.login()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        # All Exceptions get re-raised.
        if self._must_clean_session is True:
            await self.session.close()
        return exc is None

    async def _send_request(
        self, url: str, method: str = "get", **kwargs
    ) -> aiohttp.ClientResponse:
        LOGGER.debug(f"-> {method.upper()} {url} {kwargs}")
        r = await self.session.request(
            method, url, headers=AQUALINK_HTTP_HEADERS, **kwargs
        )
        if r.status == 200:
            LOGGER.debug(f"<- {r.status} {r.reason} - {url}")
        else:
            LOGGER.warning(f"<- {r.status} {r.reason} - {url}")
        return r

    async def _send_login_request(self) -> aiohttp.ClientResponse:
        data = {
            "api_key": AQUALINK_API_KEY,
            "email": self.username,
            "password": self.password,
        }
        return await self._send_request(AQUALINK_LOGIN_URL, method="post", json=data)

    async def login(self) -> None:
        r = await self._send_login_request()

        if r.status == 200:
            data = await r.json()
            self.session_id = data["session_id"]
            self.token = data["authentication_token"]
            self.user_id = data["id"]
        else:
            raise Exception(f"Login failed: {r.status} {r.reason}")

    async def _send_systems_request(self) -> aiohttp.ClientResponse:
        params = {
            "api_key": AQUALINK_API_KEY,
            "authentication_token": self.token,
            "user_id": self.user_id,
        }
        params = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{AQUALINK_DEVICES_URL}?{params}"
        return await self._send_request(url)

    async def get_systems(self) -> Dict[str, "AqualinkSystems"]:
        r = await self._send_systems_request()

        if r.status == 200:
            data = await r.json()
            systems = [AqualinkSystem.from_data(self, x) for x in data]
            return {x.serial: x for x in systems if x is not None}

        raise Exception(f"Unable to retrieve systems list: {r.status} {r.reason}")

    async def _send_session_request(
        self, serial: str, command: str, params: Optional[Payload] = None
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

    async def send_devices_screen_request(self, serial) -> aiohttp.ClientResponse:
        r = await self._send_session_request(serial, AQUALINK_COMMAND_GET_DEVICES)
        return r

    async def set_pump(self, serial: str, command: str) -> aiohttp.ClientResponse:
        r = await self._send_session_request(serial, command)
        return r

    async def set_heater(self, serial: str, command: str) -> aiohttp.ClientResponse:
        r = await self._send_session_request(serial, command)
        return r

    async def set_temps(self, serial: str, temps: Payload) -> aiohttp.ClientResponse:
        r = await self._send_session_request(serial, AQUALINK_COMMAND_SET_TEMPS, temps)
        return r

    async def set_aux(self, serial: str, aux: str) -> aiohttp.ClientResponse:
        command = AQUALINK_COMMAND_SET_AUX + "_" + aux.replace("aux_", "")
        r = await self._send_session_request(serial, command)
        return r

    async def set_light(self, serial: str, data: Payload) -> aiohttp.ClientResponse:
        r = await self._send_session_request(serial, AQUALINK_COMMAND_SET_LIGHT, data)
        return r
