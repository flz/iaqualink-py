from __future__ import annotations

import logging
from typing import TYPE_CHECKING, cast

from iaqualink.const import AQUALINK_API_KEY
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.iaqua.device import (
    _HOME_DEVICE_MAP,
    ICL_CUSTOM_COLOR_ID,
    ICL_CUSTOM_COLOR_NAME,
    IaquaAuxSwitch,
    IaquaBinaryState,
    IaquaClimate,
    IaquaDimmableLight,
    IaquaIclLight,
    IaquaLightSwitch,
    IaquaOneTouchSwitch,
    IaquaPump,
    IaquaSetPoint,
    IaquaZoneStatus,
    light_subtype_to_class,
)
from iaqualink.systems.iaqua.enums import (
    IaquaSystemStatus,
    IaquaSystemType,
    IaquaTemperatureUnit,
)
from iaqualink.utils.redact import mask_serial, redact_value

if TYPE_CHECKING:
    import httpx

    from iaqualink.client import AqualinkClient
    from iaqualink.typing import Payload

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

# ICL (IntelliCenter Light) commands
IAQUA_COMMAND_ICL_ONOFF = "onoff_iclzone"
IAQUA_COMMAND_ICL_SET_COLOR = "set_iclzone_color"
IAQUA_COMMAND_ICL_SET_CUSTOM_COLOR = "define_iclzone_customcolor"

IAQUA_COMMAND_GET_VSP_SPEED = "get_vsp_speedauxinfo"
IAQUA_COMMAND_SET_VSP_SPEED = "enable_disable_pump_speedId"
IAQUA_COMMAND_GET_VSP_NAMES = "get_vsp_names"
IAQUA_COMMAND_GET_VSP_APPMODELSERIALS = "get_vsp_appmodelserials"
IAQUA_COMMAND_GET_MASTER_DEVICE_LIST = "get_master_device_list"

LOGGER = logging.getLogger("iaqualink.systems.iaqua")


_IAQUA_STATUS_MAP: dict[str, SystemStatus] = {
    IaquaSystemStatus.ONLINE: SystemStatus.ONLINE,
    IaquaSystemStatus.OFFLINE: SystemStatus.OFFLINE,
    IaquaSystemStatus.SERVICE: SystemStatus.SERVICE,
    IaquaSystemStatus.UNKNOWN: SystemStatus.UNKNOWN,
}


class IaquaSystem(AqualinkSystem):
    NAME = "iaqua"

    def __init__(self, aqualink: AqualinkClient, data: Payload):
        super().__init__(aqualink, data)

        self.system_type: IaquaSystemType | None = None
        self.temp_unit: IaquaTemperatureUnit | None = None
        # Re-evaluated from the home response on every update() call.
        # None = home response not yet parsed; True/False = last home response value.
        self._onetouch_supported: bool | None = None
        # VSP pump discovery runs once; False = not yet run.
        self._vsp_discovered: bool = False

    @property
    def is_vsp(self) -> bool:
        return self.data.get("isVSP") == "true"

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = [f"{i}={getattr(self, i)!r}" for i in attrs]
        return f"{self.__class__.__name__}({' '.join(attrs)})"

    async def _send_session_request(
        self,
        command: str,
        params: Payload | None = None,
    ) -> httpx.Response:
        merged = {
            **(params or {}),
            "actionID": "command",
            "command": command,
            "serial": self.serial,
        }

        async def do_request() -> httpx.Response:
            request_params = {
                **merged,
                "sessionID": self.aqualink.client_id,
            }
            headers = {
                "Authorization": f"Bearer {self.aqualink.id_token}",
                "api_key": AQUALINK_API_KEY,
            }
            return await self.aqualink.send_request(
                IAQUA_SESSION_URL,
                params=request_params,
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

        # ICL info embedded in get_devices response as icl_info_list;
        # parsed by _parse_devices_response. get_icl_info times out on hardware.

        if not self.is_vsp:
            for key in [k for k in self.devices if k.startswith("vsp_pump_")]:
                del self.devices[key]
            self._vsp_discovered = False
        elif not self._vsp_discovered:
            await self._refresh_vsp_pumps()

    def _parse_home_response(self, response: httpx.Response) -> None:
        data = response.json()
        LOGGER.debug("Home body: %s", redact_value(data))

        home: dict = {}
        for x in data["home_screen"]:
            home.update(x)

        raw_status = home.get("status")
        self.status = _IAQUA_STATUS_MAP.get(
            raw_status or "", SystemStatus.UNKNOWN
        )
        LOGGER.debug(
            "Home parsed: serial=%s status=%s",
            mask_serial(self.serial),
            self.status.name,
        )
        if self.status is not SystemStatus.ONLINE:
            LOGGER.warning(
                "Status for system %s (%s) is %s.",
                mask_serial(self.serial),
                self.type,
                raw_status,
            )
            return

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
                if device_class is IaquaSetPoint and not state:
                    continue
                self.devices[name] = device_class(
                    self, {"name": name, "state": state}
                )

        for prefix in ("pool", "spa"):
            sp_key = f"{prefix}_set_point"
            htr_key = f"{prefix}_heater"
            therm_key = f"{prefix}_thermostat"
            if (
                sp_key in self.devices
                and htr_key in self.devices
                and therm_key not in self.devices
            ):
                self.devices[therm_key] = IaquaClimate(
                    self, {"name": therm_key}
                )

    def _parse_devices_response(self, response: httpx.Response) -> None:
        data = response.json()
        LOGGER.debug("Devices body: %s", redact_value(data))

        status = data["devices_screen"][0]["status"]
        if status in (IaquaSystemStatus.OFFLINE, IaquaSystemStatus.SERVICE, ""):
            LOGGER.warning(
                "Skipping device update for system %s (%s): devices_screen status is %s.",
                mask_serial(self.serial),
                self.type,
                status,
            )
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

        LOGGER.debug(
            "Devices parsed: serial=%s count=%d",
            mask_serial(self.serial),
            len(self.devices),
        )

        self._upsert_icl_zones(data.get("icl_info_list", []))

    async def set_switch(self, command: str) -> None:
        r = await self._send_session_request(command)
        self._parse_home_response(r)

    async def set_temps(self, temps: Payload) -> None:
        # Both pool and spa temperatures must be sent together in one request.
        # Seed args with current set-point values then apply the caller's override.
        args: Payload = {}
        i = 1
        if "spa_set_point" in self.devices:
            args[f"temp{i}"] = cast(
                IaquaSetPoint, self.devices["spa_set_point"]
            ).state
            i += 1
        args[f"temp{i}"] = cast(
            IaquaSetPoint, self.devices["pool_set_point"]
        ).state
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
        LOGGER.debug("OneTouch body: %s", redact_value(data))

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
                "Skipping onetouch update for system %s (%s): onetouch_screen status is %s.",
                mask_serial(self.serial),
                self.type,
                raw_ot_status,
            )
            return

        onetouch_count = 0
        for name, val in onetouch.items():
            if not isinstance(val, list) or not name.startswith("onetouch_"):
                continue
            attrs = {"name": name}
            for y in val:
                attrs.update(y)
            if attrs.get("status") == IaquaBinaryState.OFF:
                self.devices.pop(name, None)
                continue
            onetouch_count += 1
            if name in self.devices:
                for dk, dv in attrs.items():
                    self.devices[name].data[dk] = dv
            else:
                self.devices[name] = IaquaOneTouchSwitch(self, attrs)

        LOGGER.debug(
            "OneTouch parsed: serial=%s count=%d",
            mask_serial(self.serial),
            onetouch_count,
        )

    async def set_onetouch(self, name: str) -> None:
        cmd = IAQUA_COMMAND_SET_ONETOUCH + "_" + name.removeprefix("onetouch_")
        r = await self._send_session_request(cmd)
        self._parse_onetouch_response(r)

    def _upsert_icl_zones(self, icl_zones: list[dict[str, object]]) -> None:
        for zone_data in icl_zones:
            zone_id = zone_data.get("zoneId")
            if zone_id is None:
                continue
            device_name = f"icl_zone_{zone_id}"
            if zone_data.get("zoneStatus") == IaquaZoneStatus.ABSENT:
                self.devices.pop(device_name, None)
                continue
            device_data = {
                k: str(v) if v is not None else "" for k, v in zone_data.items()
            }
            if device_name in self.devices:
                self.devices[device_name].data.update(device_data)
            else:
                self.devices[device_name] = IaquaIclLight(self, device_data)

    def _parse_icl_info_response(self, response: httpx.Response) -> None:
        data = response.json()
        LOGGER.debug("ICL info body: %s", data)
        self._upsert_icl_zones(data.get("icl_info_list", []))

    async def icl_zone_on_off(self, zone_id: int, turn_on: bool) -> None:
        params: Payload = {
            "zone_id": str(zone_id),
            "on_off_action": "on" if turn_on else "off",
        }
        r = await self._send_session_request(IAQUA_COMMAND_ICL_ONOFF, params)
        self._parse_icl_info_response(r)

    async def icl_set_color(
        self, zone_id: int, color_id: int, dim_level: int = 100
    ) -> None:
        params: Payload = {
            "zone_id": str(zone_id),
            "color_id": str(color_id),
            "dim_level": str(dim_level),
        }
        r = await self._send_session_request(
            IAQUA_COMMAND_ICL_SET_COLOR, params
        )
        self._parse_icl_info_response(r)

    async def icl_set_brightness(self, zone_id: int, dim_level: int) -> None:
        # set_iclzone_color (not set_iclzone_dim) is the correct command for
        # brightness-only changes — the app uses set_iclzone_color for both
        # color and brightness adjustment; set_iclzone_dim is never exercised
        # by any observed app UI path.
        params: Payload = {
            "zone_id": str(zone_id),
            "dim_level": str(dim_level),
        }
        r = await self._send_session_request(
            IAQUA_COMMAND_ICL_SET_COLOR, params
        )
        self._parse_icl_info_response(r)

    def _parse_icl_custom_color_response(
        self, response: httpx.Response
    ) -> None:
        data = response.json()
        LOGGER.debug("ICL custom color body: %s", data)

        zone_id = data.get("zone_id")
        if zone_id is None:
            return

        device_name = f"icl_zone_{zone_id}"
        if device_name not in self.devices:
            return

        for key in ("red_val", "green_val", "blue_val", "white_val"):
            val = data.get(key)
            if val is not None:
                self.devices[device_name].data[key] = str(val)
        self.devices[device_name].data["zoneColor"] = str(ICL_CUSTOM_COLOR_ID)
        self.devices[device_name].data["zoneColorVal"] = ICL_CUSTOM_COLOR_NAME

    async def icl_set_custom_color(
        self, zone_id: int, red: int, green: int, blue: int, white: int = 0
    ) -> None:
        params: Payload = {
            "zone_id": str(zone_id),
            "red_val": str(red),
            "green_val": str(green),
            "blue_val": str(blue),
            "white_val": str(white),
        }
        r = await self._send_session_request(
            IAQUA_COMMAND_ICL_SET_CUSTOM_COLOR, params
        )
        self._parse_icl_custom_color_response(r)

    async def get_vsp_speed(self, slot_id: int = 1) -> Payload:
        r = await self._send_session_request(
            IAQUA_COMMAND_GET_VSP_SPEED, {"slot_id": str(slot_id)}
        )
        return r.json()

    async def set_vsp_speed(self, speed_id: int, slot_id: int = 1) -> Payload:
        r = await self._send_session_request(
            IAQUA_COMMAND_SET_VSP_SPEED,
            {
                "slot_id": str(slot_id),
                "speed_id": str(speed_id),
                "on_off_action": "on",
            },
        )
        return r.json()

    async def stop_vsp_pump(self, slot_id: int = 1) -> Payload:
        r = await self._send_session_request(
            IAQUA_COMMAND_SET_VSP_SPEED,
            {
                "slot_id": str(slot_id),
                "speed_id": "1",  # ignored by server when on_off_action="off"
                "on_off_action": "off",
            },
        )
        return r.json()

    async def get_vsp_names(self) -> Payload:
        r = await self._send_session_request(IAQUA_COMMAND_GET_VSP_NAMES)
        return r.json()

    async def get_vsp_appmodelserials(self) -> Payload:
        r = await self._send_session_request(
            IAQUA_COMMAND_GET_VSP_APPMODELSERIALS
        )
        return r.json()

    async def get_master_device_list(self) -> Payload:
        r = await self._send_session_request(
            IAQUA_COMMAND_GET_MASTER_DEVICE_LIST
        )
        return r.json()

    async def _refresh_vsp_pumps(self) -> None:
        names_data = await self.get_vsp_names()
        name_map: dict[int, str] = {
            int(p["pumpId"]): str(p["pumpName"])
            for p in names_data.get("vsp_names", [])
        }

        # Primary: master device list — per-device isVSP flag identifies slots
        mdl_data = await self.get_master_device_list()
        vsp_slots: list[tuple[int, str]] = [
            (int(d["id"]), str(d.get("name", "")))
            for d in mdl_data.get("deviceList", [])
            if d.get("isVSP") == "true"
        ]

        # Fallback: appmodelserials when master list yields no VSP devices
        if not vsp_slots:
            serials_data = await self.get_vsp_appmodelserials()
            vsp_slots = [
                (int(p["pumpId"]), "")
                for p in serials_data.get("vsp_app_model_serials", [])
            ]

        for pump_id, mdl_name in vsp_slots:
            device_name = f"vsp_pump_{pump_id}"
            if device_name in self.devices:
                continue
            label = name_map.get(pump_id, mdl_name or f"VSP Pump {pump_id}")
            data: Payload = {
                "name": device_name,
                "state": "0",
                "label": label,
                "slot_id": pump_id,
            }
            device = IaquaPump(self, data)
            await device.fetch_speed()
            self.devices[device_name] = device
            LOGGER.debug(
                "VSP pump discovered: serial=%s slot=%d name=%r",
                self.serial,
                pump_id,
                label,
            )

        self._vsp_discovered = True
