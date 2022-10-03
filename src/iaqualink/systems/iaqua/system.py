from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Optional

import httpx

from iaqualink.const import MIN_SECS_TO_REFRESH
from iaqualink.exception import (
    AqualinkDeviceNotSupported,
    AqualinkServiceException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems.iaqua.device import IaquaDevice
from iaqualink.typing import Payload

if TYPE_CHECKING:
    from iaqualink.client import AqualinkClient

IAQUA_SESSION_URL = "https://p-api.iaqualink.net/v1/mobile/session.json"

IAQUA_COMMAND_GET_DEVICES = "get_devices"
IAQUA_COMMAND_GET_HOME = "get_home"
IAQUA_COMMAND_GET_ONETOUCH = "get_onetouch"

IAQUA_COMMAND_SET_AUX = "set_aux"
IAQUA_COMMAND_SET_LIGHT = "set_light"
IAQUA_COMMAND_SET_POOL_HEATER = "set_pool_heater"
IAQUA_COMMAND_SET_POOL_PUMP = "set_pool_pump"
IAQUA_COMMAND_SET_SOLAR_HEATER = "set_solar_heater"
IAQUA_COMMAND_SET_SPA_HEATER = "set_spa_heater"
IAQUA_COMMAND_SET_SPA_PUMP = "set_spa_pump"
IAQUA_COMMAND_SET_TEMPS = "set_temps"


LOGGER = logging.getLogger("iaqualink")


class IaquaSystem(AqualinkSystem):
    NAME = "iaqua"

    def __init__(self, aqualink: AqualinkClient, data: Payload):
        super().__init__(aqualink, data)

        self.temp_unit: str = ""

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = ["%s=%r" % (i, getattr(self, i)) for i in attrs]
        return f'{self.__class__.__name__}({" ".join(attrs)})'

    async def _send_session_request(
        self,
        command: str,
        params: Optional[Payload] = None,
    ) -> httpx.Response:
        if not params:
            params = {}

        params.update(
            {
                "actionID": "command",
                "command": command,
                "serial": self.serial,
                "sessionID": self.aqualink.client_id,
            }
        )
        params_str = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{IAQUA_SESSION_URL}?{params_str}"
        return await self.aqualink.send_request(url)

    async def _send_home_screen_request(self) -> httpx.Response:
        r = await self._send_session_request(IAQUA_COMMAND_GET_HOME)
        return r

    async def _send_devices_screen_request(self) -> httpx.Response:
        r = await self._send_session_request(IAQUA_COMMAND_GET_DEVICES)
        return r

    async def update(self) -> None:
        # Be nice to Aqualink servers since we rely on polling.
        now = int(time.time())
        delta = now - self.last_refresh
        if delta < MIN_SECS_TO_REFRESH:
            LOGGER.debug(f"Only {delta}s since last refresh.")
            return

        try:
            r1 = await self._send_home_screen_request()
            r2 = await self._send_devices_screen_request()
        except AqualinkServiceException:
            self.online = None
            raise

        try:
            self._parse_home_response(r1)
            self._parse_devices_response(r2)
        except AqualinkSystemOfflineException:
            self.online = False
            raise

        self.online = True
        self.last_refresh = int(time.time())

    def _parse_home_response(self, response: httpx.Response) -> None:
        data = response.json()

        LOGGER.debug(f"Home response: {data}")

        if data["home_screen"][0]["status"] == "Offline":
            LOGGER.warning(f"Status for system {self.serial} is Offline.")
            raise AqualinkSystemOfflineException

        self.temp_unit = data["home_screen"][3]["temp_scale"]

        # Make the data a bit flatter.
        devices = {}
        for x in data["home_screen"][4:]:
            name = list(x.keys())[0]
            state = list(x.values())[0]
            attrs = {"name": name, "state": state}
            devices.update({name: attrs})

        for k, v in devices.items():
            if k in self.devices:
                for dk, dv in v.items():
                    self.devices[k].data[dk] = dv
            else:
                try:
                    self.devices[k] = IaquaDevice.from_data(self, v)
                except AqualinkDeviceNotSupported as e:
                    LOGGER.info("Device found was ignored: %s", e)

    def _parse_devices_response(self, response: httpx.Response) -> None:
        data = response.json()

        LOGGER.debug(f"Devices response: {data}")

        if data["devices_screen"][0]["status"] == "Offline":
            LOGGER.warning(f"Status for system {self.serial} is Offline.")
            raise AqualinkSystemOfflineException

        # Make the data a bit flatter.
        devices = {}
        for x in data["devices_screen"][3:]:
            aux = list(x.keys())[0]
            attrs = {"aux": aux.replace("aux_", ""), "name": aux}
            for y in list(x.values())[0]:
                attrs.update(y)
            devices.update({aux: attrs})

        for k, v in devices.items():
            if k in self.devices:
                for dk, dv in v.items():
                    self.devices[k].data[dk] = dv
            else:
                try:
                    self.devices[k] = IaquaDevice.from_data(self, v)
                except AqualinkDeviceNotSupported as e:
                    LOGGER.info("Device found was ignored: %s", e)

    async def set_switch(self, command: str) -> None:
        r = await self._send_session_request(command)
        self._parse_home_response(r)

    async def set_temps(self, temps: Payload) -> None:
        r = await self._send_session_request(IAQUA_COMMAND_SET_TEMPS, temps)
        self._parse_home_response(r)

    async def set_aux(self, aux: str) -> None:
        aux = IAQUA_COMMAND_SET_AUX + "_" + aux.replace("aux_", "")
        r = await self._send_session_request(aux)
        self._parse_devices_response(r)

    async def set_light(self, data: Payload) -> None:
        r = await self._send_session_request(IAQUA_COMMAND_SET_LIGHT, data)
        self._parse_devices_response(r)
