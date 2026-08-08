from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from iaqualink.const import AQUALINK_API_SIGNING_KEY
from iaqualink.system import AqualinkSystem, SystemStatus
from iaqualink.systems.tcx.device import TcxDevice
from iaqualink.systems.tcx.ws import (
    NAMESPACE_FEATURE_CIRCUIT,
    NAMESPACE_FILTRATION,
    NAMESPACE_PIB,
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
# No "PIB" command entries exist in the reference doc despite "PIB" being a
# listed namespace — inferred by the same "set<Thing>State" convention every
# other single-purpose namespace's toggle action uses. Never wire-confirmed;
# same inference precedent as _ACTION_SET_STATE above (VSP speed).
_ACTION_SET_JVA_STATE = "setJvaState"
# Confirmed action names (Main/"tcx" namespace, same as setAuxState/
# setHeatEnabled/setWaterTempSetpoint above) — per-action payload field
# shapes beyond the envelope are not documented for any of these four, same
# caveat as every other _send_command_frame call in this module.
_ACTION_SET_LVH_APP_TYPE = "setLvhAppType"
_ACTION_SET_AUX_LIGHT = "setAuxLight"
_ACTION_SET_AUX_RESET_COLOR = "setAuxResetColor"
_ACTION_SET_AUX_SETUP = "setAuxSetup"
_ACTION_SET_IS_AUX0_FREEZE_PROTECT = "setIsAux0FreezeProtect"
_ACTION_SET_FREEZE_SET_POINT = "setFreezeSetPoint"

LOGGER = logging.getLogger("iaqualink.systems.tcx")

# Speed fields (RPM) that exist on filt0/ecm0 but aren't otherwise surfaced —
# only used internally for TcxVariableSpeedPump's percentage/preset math.
# filt0.manSpd and ecm0.manSpd are confirmed distinct values on real
# hardware (not duplicates), so both get their own sensor.
_ECM0_EXTRA_SPEED_FIELDS: tuple[tuple[str, str], ...] = (
    ("manSpd", "Fan Manual Speed"),
    ("frzSpd", "Fan Freeze-Protect Speed"),
    ("prmSpd", "Fan Priming Speed"),
    ("qcSpd", "Fan Quick-Clean Speed"),
)


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
        # flows over the WS subscription, auto-started below (idempotent —
        # a no-op once a live task exists). Skip the REST fetch while it's
        # delivering fresh state; otherwise this is a plain REST
        # bootstrap/fallback poll.
        if await self._ws_refresh_gate():
            # refresh() resets self.status to IN_PROGRESS before calling
            # _refresh(); restore it from the cache the WS push already
            # derived, so the "must set status before returning" contract
            # holds on the skip path too.
            self.status = _derive_status(self._ws_reported_cache)
            return

        r = await self.send_reported_state_request()
        self._parse_shadow_response(r)

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
        # Feature-circuit/ZigBee device discovery: best-effort against
        # whatever the unified tree carries (REST main shadow, WS
        # Authorization ack, or a merged WS delta). These previously only
        # ran against a dedicated REST sub-shadow response, which is
        # confirmed non-functional against real hardware and has been
        # removed — see "Deltas vs Protocol Reference" in
        # docs/implementation/systems/tcx.md. Both guard on their own key
        # patterns, so calling them unconditionally is a safe no-op when the
        # data isn't present in `reported`.
        self._parse_fea_sub_shadow(reported)
        self._parse_zig_sub_shadow(reported)

    def _apply_reported_delta(self, delta: dict[str, Any]) -> None:
        """Merge a partial WS-pushed reported dict onto cached state and
        re-derive. Merging onto the full cached tree (rather than deriving
        status/temp_unit from the raw delta) matters: a delta that omits
        `aws`/`systemMode`/`tempSetting` would otherwise reset status to
        UNKNOWN or flip temp_unit back to "F" even though nothing changed.
        `_update_devices` is safe on partial dicts on its own (each key is
        individually guarded), but the two scalar derivations are not."""
        self._apply_reported_state(deep_merge(self._ws_reported_cache, delta))

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
        # ZigBee devices live in the `_zig` sub-shadow, keyed as top-level
        # `auxz[N]` entries (mirroring aux[N]/jva[N]) — confirmed by live
        # wire capture and protocol research. `zig` itself is the radio
        # module's own scalar status object (st/op/ty/euid/ai/bt/fw), not a
        # dict of devices keyed by address; it's intentionally left unparsed
        # here. See docs/reference/systems/tcx.md "zig / auxz[N]".
        candidates: dict[str, dict[str, Any]] = {}
        for k, v in reported.items():
            if k.startswith("auxz") and k[4:].isdigit() and isinstance(v, dict):
                candidates[k] = {"name": k, **v}
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
            filt0 = reported["filt0"]
            candidates["filt0"] = {"name": "filt0", **filt0}
            man_spd = filt0.get("manSpd")
            if man_spd is not None:
                candidates["filt0_manSpd"] = {
                    "name": "filt0_manSpd",
                    "label": "Filtration Manual Speed",
                    "value": man_spd,
                }

        if "ecm0" in reported:
            ecm0 = reported["ecm0"]
            candidates["ecm0"] = {"name": "ecm0", **ecm0}
            for wire_key, label in _ECM0_EXTRA_SPEED_FIELDS:
                val = ecm0.get(wire_key)
                if val is not None:
                    key = f"ecm0_{wire_key}"
                    candidates[key] = {
                        "name": key,
                        "label": label,
                        "value": val,
                    }

        for key, val in reported.items():
            if (
                key.startswith("aux")
                and key[3:].isdigit()
                and isinstance(val, dict)
            ):
                candidates[key] = {"name": key, **val}
                # setIsAux0FreezeProtect is the only single-purpose "tcx"
                # action with a specific aux index baked into its name
                # (unlike setAuxState/setAuxLight/setAuxSetup, which are
                # genuinely generic across aux[N]) — freeze protect is a
                # real hardware feature of the aux0 relay specifically, not
                # a capability every auxN has. Singleton, like lvh1/lvh1_enable.
                if key == "aux0":
                    fp = val.get("fp")
                    if fp is not None:
                        candidates["aux0_fp"] = {"name": "aux0_fp", "fp": fp}

        if "TspBdy0" in reported:
            # Wire `name` is the body label (e.g. "Pool"); reassign to
            # `bodyName` so it doesn't clobber the dispatch key below.
            candidates["TspBdy0"] = {
                **reported["TspBdy0"],
                "name": "TspBdy0",
                "bodyName": reported["TspBdy0"].get("name"),
            }

        if "freezeSP" in reported:
            candidates["freezeSP"] = {
                "name": "freezeSP",
                "value": reported["freezeSP"],
            }

        if "lvh1" in reported:
            lvh1 = reported["lvh1"]
            candidates["lvh1"] = {"name": "lvh1", **lvh1}
            candidates["lvh1_enable"] = {"name": "lvh1_enable", **lvh1}

        if "swc0" in reported:
            candidates["swc0"] = {"name": "swc0", **reported["swc0"]}

        if "solar" in reported:
            candidates["solar"] = {"name": "solar", **reported["solar"]}

        for key, val in reported.items():
            if (
                key.startswith("jva")
                and key[3:].isdigit()
                and isinstance(val, dict)
            ):
                candidates[key] = {"name": key, **val}

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

    async def set_zigbee_state(self, name: str, state: int) -> None:
        # Payload confirmed via protocol research against the `_zig`
        # sub-shadow's write shape: {"state": {"desired": {"auxz0": {"st":
        # 1}}}}. `name` is the auxz[N] key, not a bare zigbee address.
        await self._send_command_frame(
            namespace=NAMESPACE_ZIGBEE,
            action=_ACTION_SET_ZIGBEE_STATE,
            delta={name: {"st": state}},
        )

    async def set_jva_state(self, name: str, state: int) -> None:
        await self._send_command_frame(
            namespace=NAMESPACE_PIB,
            action=_ACTION_SET_JVA_STATE,
            delta={name: {"st": state}},
        )

    async def set_lvh_app_type(self, enabled: bool) -> None:
        await self._send_command_frame(
            namespace=NAMESPACE_TCX,
            action=_ACTION_SET_LVH_APP_TYPE,
            delta={"lvh1": {"app": "HEAT" if enabled else "OFF"}},
        )

    async def set_aux_light(self, name: str, color_index: int) -> None:
        await self._send_command_frame(
            namespace=NAMESPACE_TCX,
            action=_ACTION_SET_AUX_LIGHT,
            delta={name: {"cmdClr": color_index}},
        )

    async def reset_aux_light(self, name: str) -> None:
        # No documented fields beyond the envelope for this action — same
        # inference precedent as set_jva_state (namespace/action confirmed,
        # payload shape is not).
        await self._send_command_frame(
            namespace=NAMESPACE_TCX,
            action=_ACTION_SET_AUX_RESET_COLOR,
            delta={name: {}},
        )

    async def set_aux_setup(
        self, name: str, *, app: str, et: str, ty: int, fr: str
    ) -> None:
        await self._send_command_frame(
            namespace=NAMESPACE_TCX,
            action=_ACTION_SET_AUX_SETUP,
            delta={name: {"app": app, "et": et, "ty": ty, "fr": fr}},
        )

    async def set_aux_freeze_protect(self, enabled: bool) -> None:
        # Action name hardcodes "Aux0" — aux0-only, not generic across
        # aux[N]. See _update_devices()'s aux0_fp comment.
        await self._send_command_frame(
            namespace=NAMESPACE_TCX,
            action=_ACTION_SET_IS_AUX0_FREEZE_PROTECT,
            delta={"aux0": {"fp": enabled}},
        )

    async def set_freeze_set_point(self, temp: int) -> None:
        # freezeSP is a top-level `state.reported` field, not nested under
        # any device object (unlike TspBdy0.waterTempSet etc.) — the delta
        # mirrors that flat shape.
        await self._send_command_frame(
            namespace=NAMESPACE_TCX,
            action=_ACTION_SET_FREEZE_SET_POINT,
            delta={"freezeSP": temp},
        )
