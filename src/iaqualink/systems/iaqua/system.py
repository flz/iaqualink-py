from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from iaqualink.const import AQUALINK_API_KEY
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.iaqua.device import (
    IaquaAuxSwitch,
    IaquaBinaryState,
    IaquaDimmableLight,
    IaquaLightSwitch,
    IaquaOneTouchSwitch,
    IaquaThermostat,
    _HOME_DEVICE_MAP,
    light_subtype_to_class,
)
from iaqualink.systems.iaqua.enums import (
    IaquaSystemStatus,
    IaquaSystemType,
    IaquaTemperatureUnit,
)

if TYPE_CHECKING:
    import httpx

    from iaqualink.client import AqualinkClient
    from iaqualink.typing import Payload

# v2 session endpoint (p-api); used for all get_*/set_* commands.
# r-api hosts v1 / swc endpoints — kept here for future reference.
IAQUA_SESSION_URL = "https://p-api.iaqualink.net/v2/mobile/session.json"
IAQUA_SESSION_V1_URL = "https://r-api.iaqualink.net/v1/mobile/session.json"

IAQUA_COMMAND_GET_DEVICES = "get_devices"
IAQUA_COMMAND_GET_HOME = "get_home"
IAQUA_COMMAND_GET_ONETOUCH = "get_onetouch"

IAQUA_COMMAND_SET_AUX = "set_aux"
IAQUA_COMMAND_SET_ONETOUCH = "set_onetouch"
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

        self.system_type: IaquaSystemType | None = None
        self.temp_unit: IaquaTemperatureUnit | None = None
        # Re-evaluated from the home response on every update() call.
        # None = home response not yet parsed; True/False = last home response value.
        self._onetouch_supported: bool | None = None

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
            }
        )

        async def do_request() -> httpx.Response:
            request_params = {
                **params,
                "sessionID": self.aqualink.client_id,
            }
            params_str = "&".join(f"{k}={v}" for k, v in request_params.items())
            url = f"{IAQUA_SESSION_URL}?{params_str}"
            headers = {
                "Authorization": f"Bearer {self.aqualink.id_token}",
                "api_key": AQUALINK_API_KEY,
            }
            return await self.aqualink.send_request(
                url,
                headers=headers,
            )

        return await self._send_with_reauth_retry(do_request)

    async def _send_home_screen_request(self) -> httpx.Response:
        return await self._send_session_request(
            IAQUA_COMMAND_GET_HOME,
            {"attached_test": "true", "country": self.aqualink.country},
        )

    async def _send_devices_screen_request(self) -> httpx.Response:
        return await self._send_session_request(IAQUA_COMMAND_GET_DEVICES)

    async def _send_onetouch_screen_request(self) -> httpx.Response:
        return await self._send_session_request(IAQUA_COMMAND_GET_ONETOUCH)

    async def _refresh(self) -> None:
        # Only the home response determines system status; fetch and parse it
        # first so we can skip subsequent requests when the system is not ONLINE.
        r1 = await self._send_home_screen_request()
        self._parse_home_response(r1)
        if self.status is not SystemStatus.ONLINE:
            return

        r2 = await self._send_devices_screen_request()
        self._parse_devices_response(r2)

        if self._onetouch_supported:
            r3 = await self._send_onetouch_screen_request()
            self._parse_onetouch_response(r3)

    def _parse_home_response(self, response: httpx.Response) -> None:
        data = response.json()

        LOGGER.debug("Home response: %s", data)

        home: dict = {}
        for x in data["home_screen"]:
            home.update(x)

        raw_status = home.get("status")
        if raw_status == IaquaSystemStatus.OFFLINE:
            LOGGER.warning(
                "Status for system %s is %s.", self.serial, raw_status
            )
            self.status = SystemStatus.OFFLINE
            return
        elif raw_status == IaquaSystemStatus.SERVICE:
            LOGGER.warning(
                "Status for system %s is %s.", self.serial, raw_status
            )
            self.status = SystemStatus.SERVICE
            return
        elif raw_status in (IaquaSystemStatus.UNKNOWN, None, ""):
            LOGGER.warning(
                "Status for system %s is %s.", self.serial, raw_status
            )
            self.status = SystemStatus.UNKNOWN
            return
        elif raw_status != IaquaSystemStatus.ONLINE:
            LOGGER.warning(
                "Unknown status %r for system %s.", raw_status, self.serial
            )
            self.status = SystemStatus.UNKNOWN
            return

        self.status = SystemStatus.ONLINE

        if home["system_type"] == "":
            LOGGER.debug("Skipping home screen update with empty system_type.")
            return

        self._onetouch_supported = data.get("onetouch") == "true"

        try:
            self.system_type = IaquaSystemType(home["system_type"])
        except ValueError:
            LOGGER.warning(
                "Unknown system_type %r; ignoring.", home["system_type"]
            )

        try:
            self.temp_unit = IaquaTemperatureUnit(home["temp_scale"])
        except ValueError:
            LOGGER.warning(
                "Unknown temp_scale %r; ignoring.", home["temp_scale"]
            )

        for name, device_class in _HOME_DEVICE_MAP.items():
            if name not in home:
                continue

            state = home[name]

            if name in self.devices:
                self.devices[name].data["state"] = state
            else:
                if device_class is IaquaThermostat and not state:
                    continue
                self.devices[name] = device_class(
                    self, {"name": name, "state": state}
                )

    def _parse_devices_response(self, response: httpx.Response) -> None:
        data = response.json()

        LOGGER.debug("Devices response: %s", data)

        status = data["devices_screen"][0]["status"]
        if status in (IaquaSystemStatus.OFFLINE, IaquaSystemStatus.SERVICE, ""):
            LOGGER.warning("Status for system %s is %s.", self.serial, status)
            return

        for x in data["devices_screen"][3:]:
            for attr in next(iter(x.values())):
                if attr.get("state") == "NaN":
                    LOGGER.debug(
                        "Skipping devices screen update with NaN state."
                    )
                    return

        for x in data["devices_screen"][3:]:
            aux = next(iter(x.keys()))
            attrs = {"aux": aux.replace("aux_", ""), "name": aux}
            for y in next(iter(x.values())):
                attrs.update(y)

            if aux in self.devices:
                for dk, dv in attrs.items():
                    self.devices[aux].data[dk] = dv
            else:
                device_type = attrs.get("type", "0")
                label = attrs.get("label", "")
                if device_type == "2":
                    device_class = light_subtype_to_class[attrs["subtype"]]
                elif device_type == "1":
                    device_class = IaquaDimmableLight
                elif "LIGHT" in label:
                    device_class = IaquaLightSwitch
                else:
                    device_class = IaquaAuxSwitch
                self.devices[aux] = device_class(self, attrs)

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
        aux = IAQUA_COMMAND_SET_AUX + "_" + aux.removeprefix("aux_")
        r = await self._send_session_request(aux)
        self._parse_devices_response(r)

    async def set_light(self, data: Payload) -> None:
        r = await self._send_session_request(IAQUA_COMMAND_SET_LIGHT, data)
        self._parse_devices_response(r)

    def _parse_onetouch_response(self, response: httpx.Response) -> None:
        data = response.json()

        LOGGER.debug("OneTouch response: %s", data)

        onetouch: dict = {}
        for x in data["onetouch_screen"]:
            onetouch.update(x)

        raw_ot_status = onetouch.get("status")
        if raw_ot_status in (
            IaquaSystemStatus.OFFLINE,
            IaquaSystemStatus.SERVICE,
            "",
        ):
            LOGGER.warning(
                "Status for system %s is %s.", self.serial, raw_ot_status
            )
            return

        for name, val in onetouch.items():
            if not isinstance(val, list) or not name.startswith("onetouch_"):
                continue
            attrs = {"name": name}
            for y in val:
                attrs.update(y)
            if attrs.get("status") == IaquaBinaryState.OFF:
                self.devices.pop(name, None)
                continue
            if name in self.devices:
                for dk, dv in attrs.items():
                    self.devices[name].data[dk] = dv
            else:
                self.devices[name] = IaquaOneTouchSwitch(self, attrs)

    async def set_onetouch(self, name: str) -> None:
        cmd = IAQUA_COMMAND_SET_ONETOUCH + "_" + name.removeprefix("onetouch_")
        r = await self._send_session_request(cmd)
        self._parse_onetouch_response(r)
