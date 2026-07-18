from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING, Any

from iaqualink.const import AQUALINK_API_SIGNING_KEY
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.tcx.device import TcxDevice
from iaqualink.systems.tcx.ws import (
    NAMESPACE_FEATURE_CIRCUIT,
    NAMESPACE_FILTRATION,
    NAMESPACE_SWC,
    NAMESPACE_TCX,
    NAMESPACE_ZIGBEE,
    TcxStateSubscription,
)
from iaqualink.utils.crypto import sign
from iaqualink.utils.redact import mask_serial, redact_value
from iaqualink.utils.websockets import deep_merge

if TYPE_CHECKING:
    import httpx

    from iaqualink.client import AqualinkClient
    from iaqualink.typing import Payload

TCX_SHADOW_URL = "https://prod.zodiac-io.com/devices/v2"
TCX_SUB_SHADOW_READ_URL = "https://prod.zodiac-io.com/devices/v1"

# Wire actions (docs/reference/systems/tcx.md "Command Reference"). Per-action
# payload shapes beyond the envelope aren't documented — see _send_command_frame.
_ACTION_SET_FILTER_PUMP_STATE = "setFilterPumpState"
_ACTION_SET_AUX_STATE = "setAuxState"
_ACTION_SET_HEAT_ENABLED = "setHeatEnabled"
_ACTION_SET_WATER_TEMP_SETPOINT = "setWaterTempSetpoint"
_ACTION_SET_BOOST_MODE = "setBoostMode"
# No VSP action matches "set current commanded speed" (setPrimingSpeed/
# setMinMasterSpeed/setMaxMasterSpeed/setQuickCleanSpeed/setFreezeProtectSpeed
# are all specific-purpose) — fall back to the tcx namespace's generic action.
_ACTION_SET_STATE = "setState"
_ACTION_SET_FEATURE_CIRCUIT_STATE = "setFeatureCircuitState"
_ACTION_SET_ZIGBEE_STATE = "setZigbeeState"

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


class TcxSystem(TcxStateSubscription, AqualinkSystem):
    NAME = "tcx"

    def __init__(self, aqualink: AqualinkClient, data: Payload):
        super().__init__(aqualink, data)
        self.temp_unit = "F"
        self._ws_reported_cache: dict[str, Any] = {}

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

    async def _refresh(self) -> None:
        # Per the reference app, REST shadow GET is only a one-shot
        # online/offline status check (system list screen) — live state
        # flows over the WS subscription when a consumer has started one via
        # start_ws_subscription() (not auto-started here — the library must
        # not spin up background tasks on its own, matching cyclobat's
        # precedent). Skip the REST fetch while it's delivering fresh state;
        # otherwise this is a plain REST bootstrap/fallback poll.
        if self._ws_enabled and self._ws_state_fresh():
            # refresh() resets self.status to IN_PROGRESS before calling
            # _refresh(); restore it from the cache the WS push already
            # derived, so the "must set status before returning" contract
            # holds on the skip path too.
            self.status = _derive_status(self._ws_reported_cache)
            return

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
        self._apply_reported_state(reported)
        return reported

    def _apply_reported_state(self, reported: dict[str, Any]) -> None:
        """Apply a FULL tcx `state.reported` tree (REST shadow or WS
        Authorization ack): derive status/temp_unit and rebuild devices."""
        self._ws_reported_cache = reported

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

    def _apply_reported_delta(self, delta: dict[str, Any]) -> None:
        """Merge a partial WS-pushed reported dict onto cached state and
        re-derive. Merging onto the full cached tree (rather than deriving
        status/temp_unit from the raw delta) matters: a delta that omits
        `aws`/`systemMode`/`tempSetting` would otherwise reset status to
        UNKNOWN or flip temp_unit back to "F" even though nothing changed.
        `_update_devices` is safe on partial dicts on its own (each key is
        individually guarded), but the two scalar derivations are not."""
        self._apply_reported_state(deep_merge(self._ws_reported_cache, delta))

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

    # ── Command helpers (WS StateController frames) ──────────────────────────

    async def set_filter_pump(self, state: int) -> None:
        await self._send_command_frame(
            namespace=NAMESPACE_FILTRATION,
            action=_ACTION_SET_FILTER_PUMP_STATE,
            delta={"filt0": {"st": state}},
        )

    async def set_aux(self, name: str, state: int) -> None:
        await self._send_command_frame(
            namespace=NAMESPACE_TCX,
            action=_ACTION_SET_AUX_STATE,
            delta={name: {"st": state}},
        )

    async def set_heat_enabled(self, enabled: bool) -> None:
        await self._send_command_frame(
            namespace=NAMESPACE_TCX,
            action=_ACTION_SET_HEAT_ENABLED,
            delta={"TspBdy0": {"heatEnabled": enabled}},
        )

    async def set_water_temp_setpoint(self, temp: int) -> None:
        await self._send_command_frame(
            namespace=NAMESPACE_TCX,
            action=_ACTION_SET_WATER_TEMP_SETPOINT,
            delta={"TspBdy0": {"waterTempSet": temp}},
        )

    async def set_swc_boost(self, enabled: bool) -> None:
        await self._send_command_frame(
            namespace=NAMESPACE_SWC,
            action=_ACTION_SET_BOOST_MODE,
            delta={"swc0": {"boost": int(enabled)}},
        )

    async def set_vsp_speed(self, speed_rpm: int) -> None:
        await self._send_command_frame(
            namespace=NAMESPACE_TCX,
            action=_ACTION_SET_STATE,
            delta={"ecm0": {"cmdSpd": speed_rpm}},
        )

    async def set_feature_circuit_state(self, name: str, state: int) -> None:
        await self._send_command_frame(
            namespace=NAMESPACE_FEATURE_CIRCUIT,
            action=_ACTION_SET_FEATURE_CIRCUIT_STATE,
            delta={name: {"st": state}},
        )

    async def set_zigbee_state(self, addr: str, state: int) -> None:
        await self._send_command_frame(
            namespace=NAMESPACE_ZIGBEE,
            action=_ACTION_SET_ZIGBEE_STATE,
            delta={"zig": {addr: {"st": state}}},
        )
