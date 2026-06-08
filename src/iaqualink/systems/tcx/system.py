from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.tcx.device import TcxDevice
from iaqualink.utils.redact import mask_serial, redact_value

if TYPE_CHECKING:
    import httpx

    from iaqualink.client import AqualinkClient
    from iaqualink.typing import Payload

TCX_SHADOW_URL = "https://prod.zodiac-io.com/devices/v2"

# Sub-shadow suffixes that may exist for a given device.
# Presence is signalled by state.reported.equipment.<key>.
_SUB_SHADOW_SUFFIX_MAP = {
    "filt": "_filt",
    "ecm": "_ecm",
    "sched": "_sched",
    "pib0": "_pib0",
    "fea": "_fea",
    "zig": "_zig",
    "scene": "_scene",
}

LOGGER = logging.getLogger("iaqualink.systems.tcx")


def _derive_status(reported: dict[str, Any]) -> SystemStatus:
    system_mode = reported.get("systemMode")
    if system_mode in (3, 4):
        return SystemStatus.SERVICE

    raw = reported.get("aws", {}).get("status")
    if not raw:
        return SystemStatus.UNKNOWN

    _STATUS_MAP: dict[str, SystemStatus] = {
        "connected": SystemStatus.CONNECTED,
        "disconnected": SystemStatus.DISCONNECTED,
        "online": SystemStatus.ONLINE,
        "offline": SystemStatus.OFFLINE,
        "unknown": SystemStatus.UNKNOWN,
        "service": SystemStatus.SERVICE,
        "firmware_update": SystemStatus.FIRMWARE_UPDATE,
    }
    status = _STATUS_MAP.get(raw)
    if status is None:
        return SystemStatus.UNKNOWN
    return status


class TcxSystem(AqualinkSystem):
    NAME = "tcx"

    def __init__(self, aqualink: AqualinkClient, data: Payload):
        super().__init__(aqualink, data)
        self.temp_unit = "F"

    def __repr__(self) -> str:
        attrs = ["name", "serial", "data"]
        attrs = [f"{i}={getattr(self, i)!r}" for i in attrs]
        return f"{self.__class__.__name__}({' '.join(attrs)})"

    async def _send_shadow_request(
        self, serial: str, **kwargs: Any
    ) -> httpx.Response:
        async def do_request() -> httpx.Response:
            url = f"{TCX_SHADOW_URL}/{serial}/shadow"
            headers = {"Authorization": self.aqualink.id_token}
            return await self.aqualink.send_request(
                url, headers=headers, **kwargs
            )

        return await self._send_with_reauth_retry(do_request)

    async def send_reported_state_request(self) -> httpx.Response:
        return await self._send_shadow_request(self.serial)

    async def send_desired_state_request(
        self, state: dict[str, Any]
    ) -> httpx.Response:
        return await self._send_shadow_request(
            self.serial, method="post", json={"state": {"desired": state}}
        )

    async def _refresh(self) -> None:
        r = await self.send_reported_state_request()
        self._parse_shadow_response(r)

    def _parse_shadow_response(self, response: httpx.Response) -> None:
        data = response.json()
        LOGGER.debug("TCX shadow body: %s", redact_value(data))

        reported = data.get("state", {}).get("reported", {})

        self.status = _derive_status(reported)
        if reported.get("tempSetting") == 0:
            self.temp_unit = "C"
        else:
            self.temp_unit = "F"

        LOGGER.debug(
            "TCX shadow parsed: serial=%s status=%s",
            mask_serial(self.serial),
            self.status.name,
        )

        self._update_devices(reported)

    def _update_devices(self, reported: dict[str, Any]) -> None:
        candidates: dict[str, dict[str, Any]] = {}

        # Water temperature sensor
        if "water" in reported:
            candidates["water"] = {"name": "water", **reported["water"]}

        # Air temperature sensor
        if "airTemp" in reported:
            candidates["air"] = {
                "name": "air",
                "value": reported["airTemp"],
                "snsr": reported.get("airSnsr"),
            }

        # Filtration pump
        if "filt0" in reported:
            candidates["filt0"] = {"name": "filt0", **reported["filt0"]}

        # Variable speed pump
        if "ecm0" in reported:
            candidates["ecm0"] = {"name": "ecm0", **reported["ecm0"]}

        # Auxiliary relays — aux0..auxN (only aux0 known from spec; discover dynamically)
        for key, val in reported.items():
            if (
                key.startswith("aux")
                and key[3:].isdigit()
                and isinstance(val, dict)
            ):
                candidates[key] = {"name": key, **val}

        # Heater / temperature set-point body 0 (uppercase T — wire-level invariant)
        if "TspBdy0" in reported:
            candidates["TspBdy0"] = {
                "name": "TspBdy0",
                **reported["TspBdy0"],
            }

        # Heater tile state (drives is_heating flag)
        if "lvh1" in reported:
            candidates["lvh1"] = {"name": "lvh1", **reported["lvh1"]}

        # Salt water chlorinator
        if "swc0" in reported:
            candidates["swc0"] = {"name": "swc0", **reported["swc0"]}

        # Solar sensor
        if "solar" in reported:
            candidates["solar"] = {"name": "solar", **reported["solar"]}

        LOGGER.debug(
            "TCX devices parsed: serial=%s count=%d",
            mask_serial(self.serial),
            len(candidates),
        )

        for key, attrs in candidates.items():
            if key in self.devices:
                for dk, dv in attrs.items():
                    self.devices[key].data[dk] = dv
            else:
                self.devices[key] = TcxDevice.from_data(self, attrs)

    # ── Command helpers ──────────────────────────────────────────────────────

    async def set_filter_pump(self, state: int) -> None:
        r = await self.send_desired_state_request({"filt0": {"st": state}})
        r.raise_for_status()

    async def set_aux(self, name: str, state: int) -> None:
        r = await self.send_desired_state_request({name: {"st": state}})
        r.raise_for_status()

    async def set_heat_enabled(self, enabled: bool) -> None:
        r = await self.send_desired_state_request(
            {"TspBdy0": {"heatEnabled": enabled}}
        )
        r.raise_for_status()

    async def set_water_temp_setpoint(self, temp: int) -> None:
        r = await self.send_desired_state_request(
            {"TspBdy0": {"waterTempSet": temp}}
        )
        r.raise_for_status()

    async def set_swc_boost(self, enabled: bool) -> None:
        r = await self.send_desired_state_request(
            {"swc0": {"boost": int(enabled)}}
        )
        r.raise_for_status()

    async def set_vsp_speed(self, speed_rpm: int) -> None:
        r = await self.send_desired_state_request(
            {"ecm0": {"cmdSpd": speed_rpm}}
        )
        r.raise_for_status()
