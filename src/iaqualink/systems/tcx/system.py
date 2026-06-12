from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from iaqualink.const import AQUALINK_API_SIGNING_KEY
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.tcx.device import TcxDevice
from iaqualink.utils.crypto import sign
from iaqualink.utils.redact import mask_serial, redact_value

if TYPE_CHECKING:
    import httpx

    from iaqualink.client import AqualinkClient
    from iaqualink.typing import Payload

TCX_SHADOW_URL = "https://prod.zodiac-io.com/devices/v2"
TCX_SUB_SHADOW_READ_URL = "https://prod.zodiac-io.com/devices/v1"

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

    async def _send_sub_shadow_read_request(
        self, suffix: str
    ) -> httpx.Response:
        async def do_request() -> httpx.Response:
            url = f"{TCX_SUB_SHADOW_READ_URL}/{self.serial}{suffix}/shadow"
            headers = {"Authorization": self.aqualink.id_token}
            return await self.aqualink.send_request(url, headers=headers)

        return await self._send_with_reauth_retry(do_request)

    async def send_reported_state_request(self) -> httpx.Response:
        signature = sign(
            [self.serial.upper(), self.aqualink.user_id],
            AQUALINK_API_SIGNING_KEY,
        )
        return await self._send_shadow_request(
            self.serial, params={"signature": signature}
        )

    async def send_desired_state_request(
        self, state: dict[str, Any]
    ) -> httpx.Response:
        return await self._send_shadow_request(
            self.serial, method="post", json={"state": {"desired": state}}
        )

    async def send_sub_shadow_desired_state_request(
        self, suffix: str, state: dict[str, Any]
    ) -> httpx.Response:
        return await self._send_shadow_request(
            f"{self.serial}{suffix}",
            method="post",
            json={"state": {"desired": state}},
        )

    async def _refresh(self) -> None:
        r = await self.send_reported_state_request()
        reported = self._parse_shadow_response(r)

        suffixes = self._active_sub_shadow_suffixes(reported)
        if suffixes:
            sub_responses = await asyncio.gather(
                *[self._send_sub_shadow_read_request(s) for s in suffixes],
                return_exceptions=True,
            )
            for suffix, resp in zip(suffixes, sub_responses):
                if isinstance(resp, BaseException):
                    LOGGER.warning(
                        "TCX sub-shadow %s fetch failed for %s: %s",
                        suffix,
                        mask_serial(self.serial),
                        resp,
                    )
                    continue
                self._parse_sub_shadow_response(suffix, resp)

    def _active_sub_shadow_suffixes(
        self, reported: dict[str, Any]
    ) -> list[str]:
        equipment = reported.get("equipment", {})
        return [s for k, s in _SUB_SHADOW_SUFFIX_MAP.items() if k in equipment]

    def _parse_shadow_response(
        self, response: httpx.Response
    ) -> dict[str, Any]:
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
        return reported

    def _parse_sub_shadow_response(
        self, suffix: str, response: httpx.Response
    ) -> None:
        data = response.json()
        LOGGER.debug("TCX sub-shadow %s body: %s", suffix, redact_value(data))
        reported = data.get("state", {}).get("reported", {})

        if suffix == "_filt":
            self._merge_device_data("filt0", reported)
        elif suffix == "_ecm":
            self._merge_device_data("ecm0", reported)
        elif suffix == "_fea":
            self._parse_fea_sub_shadow(reported)
        elif suffix == "_zig":
            self._parse_zig_sub_shadow(reported)
        # _sched, _pib0, _scene: fetched but schema not confirmed; not surfaced

    def _merge_device_data(self, key: str, reported: dict[str, Any]) -> None:
        if key in self.devices:
            self.devices[key].data.update(reported)

    def _parse_fea_sub_shadow(self, reported: dict[str, Any]) -> None:
        candidates: dict[str, dict[str, Any]] = {}
        for k, v in reported.items():
            if (
                k.startswith("feaCircuit")
                and k[10:].isdigit()
                and isinstance(v, dict)
            ):
                candidates[k] = {"name": k, **v}
        self._upsert_devices(candidates)

    def _parse_zig_sub_shadow(self, reported: dict[str, Any]) -> None:
        zig = reported.get("zig", {})
        if not isinstance(zig, dict):
            return
        candidates: dict[str, dict[str, Any]] = {}
        for addr, v in zig.items():
            if isinstance(v, dict):
                key = f"zig_{addr}"
                candidates[key] = {"name": key, "addr": addr, **v}
        self._upsert_devices(candidates)

    def _update_devices(self, reported: dict[str, Any]) -> None:
        candidates: dict[str, dict[str, Any]] = {}

        if "water" in reported:
            candidates["water"] = {"name": "water", **reported["water"]}

        if "airTemp" in reported:
            candidates["air"] = {
                "name": "air",
                "value": reported["airTemp"],
                "snsr": reported.get("airSnsr"),
            }

        if "filt0" in reported:
            candidates["filt0"] = {"name": "filt0", **reported["filt0"]}

        if "ecm0" in reported:
            candidates["ecm0"] = {"name": "ecm0", **reported["ecm0"]}

        for key, val in reported.items():
            if (
                key.startswith("aux")
                and key[3:].isdigit()
                and isinstance(val, dict)
            ):
                candidates[key] = {"name": key, **val}

        if "TspBdy0" in reported:
            # Wire `name` is the body label (e.g. "Pool"); reassign to
            # `bodyName` so it doesn't clobber the dispatch key below.
            candidates["TspBdy0"] = {
                **reported["TspBdy0"],
                "name": "TspBdy0",
                "bodyName": reported["TspBdy0"].get("name"),
            }

        if "lvh1" in reported:
            candidates["lvh1"] = {"name": "lvh1", **reported["lvh1"]}

        if "swc0" in reported:
            candidates["swc0"] = {"name": "swc0", **reported["swc0"]}

        if "solar" in reported:
            candidates["solar"] = {"name": "solar", **reported["solar"]}

        LOGGER.debug(
            "TCX devices parsed: serial=%s count=%d",
            mask_serial(self.serial),
            len(candidates),
        )

        self._upsert_devices(candidates)

    def _upsert_devices(self, candidates: dict[str, dict[str, Any]]) -> None:
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

    async def set_feature_circuit_state(self, name: str, state: int) -> None:
        r = await self.send_sub_shadow_desired_state_request(
            "_fea", {name: {"st": state}}
        )
        r.raise_for_status()

    async def set_zigbee_state(self, addr: str, state: int) -> None:
        r = await self.send_sub_shadow_desired_state_request(
            "_zig", {"zig": {addr: {"st": state}}}
        )
        r.raise_for_status()
