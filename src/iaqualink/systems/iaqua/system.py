from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, List

from iaqualink.const import MIN_SECS_TO_REFRESH
from iaqualink.exception import (
    AqualinkDeviceNotSupported,
    AqualinkServiceException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems.iaqua.device import IaquaDevice
from iaqualink.onetouch import parse_onetouch_response

if TYPE_CHECKING:
    import httpx

    from iaqualink.client import AqualinkClient
    from iaqualink.typing import Payload

IAQUA_SESSION_URL_TEMPLATE = "https://p-api.iaqualink.net/v{api_version}/mobile/session.json"

IAQUA_COMMAND_GET_DEVICES = "get_devices"
IAQUA_COMMAND_GET_HOME = "get_home"
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
        self.last_refresh: int = 0

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = [f"{i}={getattr(self, i)!r}" for i in attrs]
        return f"{self.__class__.__name__}({' '.join(attrs)})"

    async def _send_session_request(
        self,
        command: str,
        params: Payload | None = None,
        api_version: int = 1,
    ) -> httpx.Response:
        if not params:
            params = {}

        base_request_params: dict[str, Any] = {
            "actionID": "command",
            "command": command,
            "serial": self.serial,
        }

        if api_version == 1:
            base_request_params["sessionID"] = self.aqualink.client_id
        
        final_params = {**base_request_params, **params}

        params_str = "&".join(f"{k}={v}" for k, v in final_params.items())
        
        url = f"{IAQUA_SESSION_URL_TEMPLATE.format(api_version=api_version)}?{params_str}"

        custom_headers = {}
        if api_version == 2:
            if not self.aqualink._id_token:
                raise AqualinkServiceException("ID token is missing for V2 API request.")
            custom_headers["authorization"] = self.aqualink._id_token

        return await self.aqualink.send_request(url, headers=custom_headers if custom_headers else None)

    async def _send_session_post_request(
        self,
        command: str,
        json_payload_additions: Payload | None = None,
        api_version: int = 1,
    ) -> httpx.Response:
        """Helper to send POST requests to the session endpoint, handling versioning and auth."""
        if not self.aqualink._client: # Ensure client is there, though send_request also checks
            raise AqualinkServiceException("HTTP client not initialized.")

        url = IAQUA_SESSION_URL_TEMPLATE.format(api_version=api_version)

        # Base payload
        payload: dict[str, Any] = {
            "actionID": "command",
            "command": command,
            "serial": self.serial,
        }
        if api_version == 1:
            payload["sessionID"] = self.aqualink.client_id

        # Merge any additional payload items
        if json_payload_additions:
            payload.update(json_payload_additions)

        custom_headers: dict[str, str] = {
            "content-type": "application/json" # POST requests need this
        }
        if api_version == 2:
            if not self.aqualink._id_token:
                raise AqualinkServiceException("ID token is missing for V2 API POST request.")
            custom_headers["authorization"] = self.aqualink._id_token
        
        # AqualinkClient.send_request will merge these with its base headers.
        return await self.aqualink.send_request(url, method="post", headers=custom_headers, json=payload)

    async def _send_home_screen_request(self) -> httpx.Response:
        return await self._send_session_request(IAQUA_COMMAND_GET_HOME)

    async def _send_devices_screen_request(self) -> httpx.Response:
        return await self._send_session_request(IAQUA_COMMAND_GET_DEVICES)

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
            name = next(iter(x.keys()))
            state = next(iter(x.values()))
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
                    LOGGER.debug("Device found was ignored: %s", e)

    def _parse_devices_response(self, response: httpx.Response) -> None:
        data = response.json()

        LOGGER.debug(f"Devices response: {data}")

        if data["devices_screen"][0]["status"] == "Offline":
            LOGGER.warning(f"Status for system {self.serial} is Offline.")
            raise AqualinkSystemOfflineException

        # Make the data a bit flatter.
        devices = {}
        for x in data["devices_screen"][3:]:
            aux = next(iter(x.keys()))
            attrs = {"aux": aux.replace("aux_", ""), "name": aux}
            for y in next(iter(x.values())):
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
        # I'm not proud of this. If you read this, please submit a PR to make it better.
        # We need to pass the temperatures for both pool and spa (if present) in the same request.
        # Set args to current target temperatures and override with the request payload.
        args = {}
        i = 1
        if "spa_set_point" in self.devices:
            args[f"temp{i}"] = self.devices["spa_set_point"].target_temperature
            i += 1
        args[f"temp{i}"] = self.devices["pool_set_point"].target_temperature
        args.update(temps)

        r = await self._send_session_request(IAQUA_COMMAND_SET_TEMPS, args)
        self._parse_home_response(r)

    async def set_aux(self, aux: str) -> None:
        aux = IAQUA_COMMAND_SET_AUX + "_" + aux.replace("aux_", "")
        r = await self._send_session_request(aux)
        self._parse_devices_response(r)

    async def set_light(self, data: Payload) -> None:
        r = await self._send_session_request(IAQUA_COMMAND_SET_LIGHT, data)
        self._parse_devices_response(r)

    async def get_onetouch(self) -> List[dict[str, Any]]:
        """Fetch the OneTouch switches for this system."""
        # Ensure prerequisites for V2 API call are met by _send_session_request internal checks
        # serial and actionID are part of the base params in _send_session_request
        response = await self._send_session_request(
            command="get_onetouch", 
            api_version=2
        )
        # _send_session_request and subsequently AqualinkClient.send_request handle raise_for_status
        json_data = response.json()
        return parse_onetouch_response(json_data)

    async def set_onetouch(self, index: int) -> List[dict[str, Any]]:
        """Toggle a OneTouch switch by index (1-based)."""
        # Ensure prerequisites for V2 API call are met by _send_session_post_request internal checks
        command = f"set_onetouch_{index}"
        response = await self._send_session_post_request(
            command=command, 
            api_version=2
        )
        # _send_session_post_request and subsequently AqualinkClient.send_request handle raise_for_status
        json_data = response.json()
        return parse_onetouch_response(json_data)
