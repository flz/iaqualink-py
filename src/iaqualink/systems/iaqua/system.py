from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

from iaqualink.const import MIN_SECS_TO_REFRESH
from iaqualink.exception import (
    AqualinkDeviceNotSupported,
    AqualinkServiceException,
    AqualinkSystemOfflineException,
)
from iaqualink.system import AqualinkSystem
from iaqualink.systems.iaqua.device import IaquaDevice

if TYPE_CHECKING:
    import httpx

    from iaqualink.client import AqualinkClient
    from iaqualink.typing import Payload

IAQUA_SESSION_URL = "https://p-api.iaqualink.net/v1/mobile/session.json"

IAQUA_COMMAND_GET_DEVICES = "get_devices"
IAQUA_COMMAND_GET_HOME = "get_home"
IAQUA_COMMAND_GET_ONETOUCH = "get_onetouch"
IAQUA_COMMAND_GET_ICL_INFO = "get_icl_info"

IAQUA_COMMAND_SET_AUX = "set_aux"
IAQUA_COMMAND_SET_LIGHT = "set_light"
IAQUA_COMMAND_SET_POOL_HEATER = "set_pool_heater"
IAQUA_COMMAND_SET_POOL_PUMP = "set_pool_pump"
IAQUA_COMMAND_SET_SOLAR_HEATER = "set_solar_heater"
IAQUA_COMMAND_SET_SPA_HEATER = "set_spa_heater"
IAQUA_COMMAND_SET_SPA_PUMP = "set_spa_pump"
IAQUA_COMMAND_SET_TEMPS = "set_temps"

# ICL (IntellliCenter Light) commands
IAQUA_COMMAND_ICL_ONOFF = "onoff_iclzone"
IAQUA_COMMAND_ICL_SET_COLOR = "set_iclzone_color"
IAQUA_COMMAND_ICL_SET_DIM = "set_iclzone_dim"
IAQUA_COMMAND_ICL_SET_CUSTOM_COLOR = "define_iclzone_customcolor"


LOGGER = logging.getLogger("iaqualink")


class IaquaSystem(AqualinkSystem):
    NAME = "iaqua"

    def __init__(self, aqualink: AqualinkClient, data: Payload):
        super().__init__(aqualink, data)

        self.temp_unit: str = ""
        self.last_refresh: int = 0
        self.has_icl: bool = False

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = [f"{i}={getattr(self, i)!r}" for i in attrs]
        return f"{self.__class__.__name__}({' '.join(attrs)})"

    async def _send_session_request(
        self,
        command: str,
        params: Payload | None = None,
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

        # Fetch ICL info if ICL lights are present
        if self.has_icl:
            try:
                r3 = await self._send_icl_info_request()
                self._parse_icl_info_response(r3)
            except AqualinkServiceException:
                LOGGER.warning("Failed to fetch ICL info")

        self.online = True
        self.last_refresh = int(time.time())

    def _parse_home_response(self, response: httpx.Response) -> None:
        data = response.json()

        LOGGER.debug(f"Home response: {data}")

        if data["home_screen"][0]["status"] == "Offline":
            LOGGER.warning(f"Status for system {self.serial} is Offline.")
            raise AqualinkSystemOfflineException

        self.temp_unit = data["home_screen"][3]["temp_scale"]

        # Check for ICL (IntellliCenter Light) presence
        for item in data["home_screen"]:
            if isinstance(item, dict) and "is_icl_present" in item:
                # Value can be "1" or "present" depending on firmware
                self.has_icl = item["is_icl_present"] in ("1", "present")
                break

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
        from iaqualink.systems.iaqua.device import IaquaIclLight

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

        # Parse ICL info if present in devices response
        icl_zones = data.get("icl_info_list", [])
        for zone_data in icl_zones:
            zone_id = zone_data.get("zoneId", zone_data.get("zone_id"))
            if zone_id is None:
                continue

            device_name = f"icl_zone_{zone_id}"
            device_data = {k: str(v) if v is not None else "" for k, v in zone_data.items()}

            if device_name in self.devices:
                for dk, dv in device_data.items():
                    self.devices[device_name].data[dk] = dv
            else:
                self.devices[device_name] = IaquaIclLight(self, device_data)
                LOGGER.debug(f"Created ICL device: {device_name}")

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

    # ICL (IntellliCenter Light) methods

    async def _send_icl_info_request(self) -> httpx.Response:
        """Send a request to get ICL zone information."""
        return await self._send_session_request(IAQUA_COMMAND_GET_ICL_INFO)

    def _parse_icl_info_response(self, response: httpx.Response) -> None:
        """Parse the ICL info response and create/update ICL devices."""
        # Import here to avoid circular import
        from iaqualink.systems.iaqua.device import IaquaIclLight

        data = response.json()
        LOGGER.debug(f"ICL info response: {data}")

        icl_zones = data.get("icl_info_list", [])
        for zone_data in icl_zones:
            zone_id = zone_data.get("zoneId", zone_data.get("zone_id"))
            if zone_id is None:
                continue

            device_name = f"icl_zone_{zone_id}"

            # Convert zone_data to string values for DeviceData compatibility
            device_data = {k: str(v) if v is not None else "" for k, v in zone_data.items()}

            if device_name in self.devices:
                # Update existing device
                for dk, dv in device_data.items():
                    self.devices[device_name].data[dk] = dv
            else:
                # Create new ICL device
                self.devices[device_name] = IaquaIclLight(self, device_data)

    async def icl_zone_on_off(self, zone_id: int, turn_on: bool) -> None:
        """Turn an ICL zone on or off.

        Args:
            zone_id: The zone ID (1-4)
            turn_on: True to turn on, False to turn off
        """
        params: Payload = {
            "zone_id": str(zone_id),
            "on_off_action": "on" if turn_on else "off",
        }
        r = await self._send_session_request(IAQUA_COMMAND_ICL_ONOFF, params)
        self._parse_icl_info_response(r)

    async def icl_set_color(
        self, zone_id: int, color_id: int, dim_level: int = 100
    ) -> None:
        """Set an ICL zone to a preset color.

        Args:
            zone_id: The zone ID (1-4)
            color_id: The preset color ID (0-16)
            dim_level: Brightness level (0-100)
        """
        params: Payload = {
            "zone_id": str(zone_id),
            "color_id": str(color_id),
            "dim_level": str(dim_level),
        }
        r = await self._send_session_request(IAQUA_COMMAND_ICL_SET_COLOR, params)
        self._parse_icl_info_response(r)

    async def icl_set_brightness(self, zone_id: int, dim_level: int) -> None:
        """Set an ICL zone brightness.

        Args:
            zone_id: The zone ID (1-4)
            dim_level: Brightness level (0-100)
        """
        params: Payload = {
            "zone_id": str(zone_id),
            "dim_level": str(dim_level),
        }
        r = await self._send_session_request(IAQUA_COMMAND_ICL_SET_DIM, params)
        self._parse_icl_info_response(r)

    async def icl_set_custom_color(
        self, zone_id: int, red: int, green: int, blue: int, white: int = 0
    ) -> None:
        """Set an ICL zone to a custom RGB(W) color.

        Args:
            zone_id: The zone ID (1-4)
            red: Red value (0-255)
            green: Green value (0-255)
            blue: Blue value (0-255)
            white: White value (0-255)
        """
        params: Payload = {
            "zone_id": str(zone_id),
            "red_val": str(red),
            "green_val": str(green),
            "blue_val": str(blue),
            "white_val": str(white),
        }
        r = await self._send_session_request(IAQUA_COMMAND_ICL_SET_CUSTOM_COLOR, params)
        self._parse_icl_info_response(r)
