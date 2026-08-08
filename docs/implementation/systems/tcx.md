# TCX Implementation Notes

Implementation details for the TCX system (`device_type: "tcx"`). For the wire-level protocol, see [Protocol Reference: TCX](../../reference/systems/tcx.md).

## Overview

| Property | Value |
|----------|-------|
| `device_type` | `tcx` |
| API host | `prod.zodiac-io.com` (REST), `prod-socket.zodiac-io.com` (WS) |
| Authentication | JWT `IdToken` (Bearer on REST; bare on WS) |
| Update call | WS state subscription (primary, auto-started); main shadow (`GET /devices/v2/{serial}/shadow`) as a one-shot bootstrap/fallback |
| State updates | WS `StateController` command frames |
| Python class | `TcxSystem` in `src/iaqualink/systems/tcx/system.py` |

## System Status Lifecycle

Status is derived from two fields in `state.reported`:

1. `systemMode` — checked first; values `3` or `4` → `SERVICE` (remote control disabled)
2. `aws.status` — string-mapped to `SystemStatus`

### Status mapping

| Condition | `SystemStatus` |
|-----------|----------------|
| `systemMode` = `3` or `4` | `SERVICE` |
| `aws.status` = `"connected"` | `CONNECTED` |
| `aws.status` = `"disconnected"` | `DISCONNECTED` |
| `aws.status` = `"online"` | `ONLINE` |
| `aws.status` = `"offline"` | `OFFLINE` |
| `aws.status` = `"unknown"` | `UNKNOWN` |
| `aws.status` = `"service"` | `SERVICE` |
| `aws.status` = `"firmware_update"` | `FIRMWARE_UPDATE` |
| `aws.status` absent or empty | `UNKNOWN` |
| unrecognised value | `UNKNOWN` |

### Request-level status

| Condition | `SystemStatus` |
|-----------|----------------|
| Network / HTTP error (non-401) | `DISCONNECTED` |
| HTTP 429 (throttled) | `UNKNOWN` |

## Device Inventory

### From main shadow (`state.reported`)

| Shadow key | Python class | Base type | Notes |
|---|---|---|---|
| `water` | `TcxWaterSensor` | `AqualinkSensor` | Value empty when `us` ≠ `VALID` |
| `air` (from `airTemp`) | `TcxAirSensor` | `AqualinkSensor` | Synthesised from `airTemp` + `airSnsr` |
| `filt0` | `TcxFilterPump` | `AqualinkSwitch` | On/off via `filt0.st` |
| `ecm0` | `TcxVariableSpeedPump` | `AqualinkFan` | Presets from `spdList`; speed % mapped to `minSpd`–`maxSpd` |
| `aux0`…`auxN` | `TcxAuxSwitch` or `TcxAuxLight` | `AqualinkSwitch` / `AqualinkLight` | Discovered dynamically by key pattern `aux[0-9]+`; `TcxAuxLight` when `et` is `JL`/`IB`/`PSS`/`HU` (color-capable — see `LightType`), else `TcxAuxSwitch` |
| `TspBdy0` | `TcxClimate` | `AqualinkClimate` | Uppercase T — wire-level invariant |
| `TspBdy0.solarTempSet` (synthetic key `TspBdy0_solar`) | `TcxSolarSetPoint` | `AqualinkNumber` | Writable — see "Solar heater set point" below |
| `lvh1` | `TcxHeaterStatusSensor` | `AqualinkSensor` | Read-only heater-tile status, translated from `en` — see "Heater tile (`lvh1`)" below |
| `lvh1` (synthetic key `lvh1_enable`) | `TcxHeaterEnableSwitch` | `AqualinkSwitch` | Enable/disable via `app` ("HEAT"/"OFF") — sibling of `TcxHeaterStatusSensor`, same source dict |
| `aux0.fp` (synthetic key `aux0_fp`) | `TcxAuxFreezeProtectSwitch` | `AqualinkSwitch` | Freeze-protect toggle, aux0-only (singleton) — see "Aux freeze protect" below |
| `freezeSP` | `TcxFreezeSetPoint` | `AqualinkNumber` | Top-level field, not nested under any device object — see "Freeze-protection set point" below |
| `swc0` | `TcxChlorinatorBoost` | `AqualinkSwitch` | Exposes boost on/off only |
| `solar` | `TcxSolarSensor` | `AqualinkSensor` | Solar temperature |
| `filt0.manSpd` (synthetic key `filt0_manSpd`) | `TcxSpeedSensor` | `AqualinkSensor` | Raw RPM, no scaling; distinct value from `ecm0.manSpd` — confirmed not a duplicate on real hardware |
| `ecm0.manSpd`/`frzSpd`/`prmSpd`/`qcSpd` (synthetic keys `ecm0_manSpd` etc.) | `TcxSpeedSensor` | `AqualinkSensor` | Raw RPM. `minSpd`/`maxSpd`/`cmdSpd` intentionally not duplicated as sensors — already back `TcxVariableSpeedPump.percentage`/`preset_mode` |
| `jva1`…`jvaN` | `TcxJvaSwitch` | `AqualinkSwitch` | Discovered dynamically by key pattern `jva[0-9]+`; write path inferred, never wire-confirmed — see "JVA valves" below |

### Feature-circuit / ZigBee discovery (WS-driven)

`TcxFeatureCircuit` (one per `feaCircuit[N]` key) and `TcxZigbeeSwitch` (one per top-level `auxz[N]` key) used to be discovered from dedicated REST sub-shadow responses (`_fea`, `_zig`). That REST sub-shadow fetch (`/devices/v1/{serial}{suffix}/shadow`, one GET per active suffix reported under `state.reported.equipment`) is **confirmed non-functional against real hardware** and has been removed.

`_parse_fea_sub_shadow`/`_parse_zig_sub_shadow` now run unconditionally against whatever reported tree `_apply_reported_state` sees — the REST main shadow, a WS Authorization full-state ack, or a WS delta merged onto the cached tree. Both guard on their own key patterns, so this is a safe no-op when the data isn't present.

- **ZigBee (confirmed):** `_parse_zig_sub_shadow` scans for top-level `auxz[0-9]+` keys — this is the real wire shape, confirmed by live wire capture and protocol research (see "ZigBee device location" in the protocol reference's "Not Observed" table, now resolved). The `_zig` sub-shadow's `zig` key itself (radio-module scalar status, not a device) is intentionally left unparsed. The WS Authorization payload's `"zig"` namespace reliably carries this — no client-side subscribe/trigger-fetch step is needed (see "Sub-shadow delivery over WS" below).
- **Feature circuits (still unconfirmed, separately scoped):** `_parse_fea_sub_shadow` still scans for `feaCircuit[0-9]+` keys, which live wire capture shows does **not** match real hardware — the real key is `fcr[N]` (e.g. `fcr0`). This remains a known, not-yet-fixed gap (see Deltas table); feature circuits will not be discovered on hardware matching this shape.

#### Sub-shadow delivery over WS

The reference app's raw-MQTT flow gates each sub-shadow (including `_zig`) behind an `equipment.<name>` presence flag in the main shadow, then explicitly subscribes to that sub-shadow's `get/accepted`/`update/accepted` topics and publishes an empty payload to `get` to trigger the first fetch (see "MQTT Topics" in the protocol reference). This library does not replicate that flow: it only talks to the WS gateway (`TcxStateSubscription`/`WsStateSubscription`), whose `Authorization` full-state frame already delivers a fixed set of ~8 namespaces — including `zig` — unconditionally merged into one flat `reported` dict (`ws.py`'s `_reported_from_payload`), confirmed by live wire capture with no app-equivalent subscribe step taken by this client. Live updates after the initial full state ride the same generic `StateStreamer`/`DataStreamer`/`EventStreamer` delta-push path already used by every other namespace — no ZigBee-specific subscription code is needed. Whether that generic delta-frame payload shape (as opposed to the confirmed Authorization full-state shape) is namespace-keyed or flat has not been directly observed for *any* namespace (see Deltas table); `_reported_from_payload` supports both, so either resolves correctly if/when confirmed.

The `_filt`/`_ecm` sub-shadow responses used to additionally enrich `filt0`/`ecm0` device data with fields beyond what the main shadow's `reported.filt0`/`reported.ecm0` carries. That enrichment had no safe equivalent once the REST fetch was removed (the sub-shadow response's own document root *was* the flat filt0/ecm0 field set, a different shape than the nested `reported.filt0`/`reported.ecm0` the main shadow and `_update_devices()` use) and was dropped rather than reintroduced. `_update_devices()`'s existing handling of `reported.filt0`/`reported.ecm0` still picks up whatever fields land there via the main shadow or WS.

`_sched`, `_pib0`, `_scene` sub-shadows were fetched but never parsed into devices even before this change — no functionality is lost there.

## Design Decisions

### WebSocket-primary reads and writes

Per the reference app, REST shadow GET is only a one-shot online/offline status check on the system list screen — it is not part of the live data flow, and commands are issued over WebSocket. `TcxSystem` mixes in `TcxStateSubscription` (`src/iaqualink/systems/tcx/ws.py`), built on the shared `WsStateSubscription` engine (`src/iaqualink/utils/websockets.py`, also used by `cyclobat`'s `RobotStateSubscription`):

- `_refresh()` calls `_ws_refresh_gate()`, which auto-starts the WS subscription (idempotent — a no-op once a live task exists) and skips the REST fetch while `_ws_state_fresh()` is true. `AqualinkClient.close()` stops any subscriptions it auto-started (systems register themselves with the client on `start_ws_subscription()`), so a consumer that never calls `stop_ws_subscription()` itself doesn't leak a background task + connection.
- All 16 write methods (`set_filter_pump`, `set_aux`, `set_heat_enabled`, `set_water_temp_setpoint`, `set_solar_temp_setpoint`, `set_swc_boost`, `set_vsp_speed`, `set_feature_circuit_state`, `set_zigbee_state`, `set_jva_state`, `set_lvh_app_type`, `set_aux_light`, `reset_aux_light`, `set_aux_setup`, `set_aux_freeze_protect`, `set_freeze_set_point`) send WS `StateController` command frames (`service`/`namespace`/`action`/`target`/`payload`) instead of REST POST. Writes are fire-and-forget (best-effort ack, no synchronous error) — wire-level errors are signaled asynchronously via `ErrorStreamer`, not yet wired into an exception on the calling command.

This start/stop lifecycle binding (tied to `_refresh()` calls and client close) is a library design choice, not observed from the reference app — no vendor evidence documents the reference app's actual WS session lifetime.

Unlike cyclobat, tcx has no "robot" wrapper concept in its shadow — the reported tree is flat and multi-key across ~9 namespaces (see the protocol reference) — so `TcxStateSubscription` implements the generic engine's hooks directly against the whole reported tree rather than drilling into a sub-object.

**Confirmed from live wire traffic:** the Authorization full-state payload is namespace-keyed — `{<ns>: {"state": {"reported": {...}}, "metadata": {...}, "version": N, "timestamp": T}, ...}` for namespaces `main`, `filt`, `ecm`, `pib0`, `zig`, `fea`, `sched`, `scene` — not a single flat `payload["state"]["reported"]` as originally assumed. `_reported_from_payload()` (`src/iaqualink/systems/tcx/ws.py`) merges every namespace's `reported` tree into one flat dict before handing it to `_apply_reported_state`, matching what `_update_devices`/`_parse_fea_sub_shadow`/`_parse_zig_sub_shadow` expect. Before this fix, the mismatch meant `_ws_full_state_from_frame` always returned `None`: the WS push was silently dropped, `_ws_state_fresh()` never became true, and `_refresh()` fell back to REST every time despite auto-starting the subscription — live-verified against real hardware (device count went from 1 to 7 after the fix).

**Still unconfirmed** (see Deltas table below): the `StateStreamer`/`DataStreamer`/`EventStreamer` delta payload shape (not directly observed — `_reported_from_payload()` supports both the flat and namespace-keyed shapes defensively), and per-action WS command payload field shapes.

### Shadow URL versions

TCX main shadow reads use `/devices/v2/` (spec §Shadow Endpoints). All writes use `/devices/v2/`. Sub-shadow reads (`/devices/v1/` with the suffixed serial) are no longer issued by this library — see "Feature-circuit / ZigBee discovery" above.

### HMAC signature on main shadow GET

The main shadow GET (`/devices/v2/{serial}/shadow`) requires `?signature={sig}` or the request is rejected with `400 BAD_REQUEST` (`"missing signature"`). `sig` is `sign([serial.upper(), user_id], AQUALINK_API_SIGNING_KEY)` — the same HMAC-SHA1 helper and signing key used for device discovery, with `[serial.upper(), user_id]` as the message parts. Writes (`POST`) do not require a signature.

### Temperature unit

`state.reported.tempSetting` encodes unit: `0` = °C, `1` = °F. The implementation reads this field and stores it on `TcxSystem.temp_unit`. Default is `"F"` if the field is absent.

### Temperature wire scaling (tenths of a degree)

Confirmed from live wire capture: `waterTempSet`, `water.value`, `solar.value`, `freezeSP`, and `lowAirSP` are all tenths of the active display unit (whichever `tempSetting` selects), not whole degrees. `freezeSP=33` and `lowAirSP=128` only make sense as `3.3`/`12.8` (freeze protection and a low-air cutoff near freezing/mild), not `33`/`128`; `waterTempSet` and `water.value` agreeing at raw `283` only makes sense as `28.3°C` for both, not `283°C`. `_wire_temp_to_display()`/`_display_temp_to_wire()` (`src/iaqualink/systems/tcx/device.py`) convert on read (`TcxWaterSensor.value`, `TcxSolarSensor.value`, `TcxClimate.target_temperature`) and on write (`TcxClimate._set_temperature`, before calling `TcxSystem.set_water_temp_setpoint`, which stays a raw passthrough like every other `set_*` system method). `TcxClimate.min_temp`/`max_temp` are unaffected — they're whole-degree display bounds, not wire values.

`TcxAirSensor` is **not** scaled — it's part of delta #9 below (unreachable on real hardware today; needs its own fix first, and should get the same scaling treatment then).

### JVA valves

`jva1`/`jva2` (JVA valve actuators) live under the `pib0` namespace on real hardware — confirmed via live wire capture, and the reference doc already has an accurate, decompiled-source-derived schema for them (`### jva1 / jva2 (JVA Valve Actuators)`). They were never wired into `_update_devices()`; now discovered dynamically by key pattern `jva[0-9]+`, matching the existing `aux[0-9]+` loop exactly, and modeled as `TcxJvaSwitch` (on/off via `st`).

No "PIB" command entries exist anywhere in the reference doc's Command Reference section, despite "PIB" being a listed namespace — so `set_jva_state`'s namespace/action (`NAMESPACE_PIB`/`"setJvaState"`) is inferred, following the `"set<Thing>State"` convention every other single-purpose namespace's toggle action uses. Never wire-confirmed; same inference precedent as `set_vsp_speed` (Delta #8). Not exercised against real hardware — covered by mocked tests only.

Two related `pib0`-namespace sub-objects are deliberately **not** modeled: `spare` (not confirmed to be in active use on any observed hardware — live value is a `-1311` sentinel with an undocumented `us=0` status, and the reference doc has only a one-line stub, no confirmed sub-object schema) and `pib0`'s own board-identity metadata (`sn`/`vr`/`pibConfig`/`app`) — consistent with the earlier decision not to model the `zig` namespace's own radio-metadata block as a device.

### Heater tile (`lvh1`)

`lvh1` ("light/valve/heater 1", the pib0-namespace heater-tile object — see protocol reference) is modeled as **two sibling devices**, not folded into `TcxClimate`: `TcxHeaterStatusSensor` (`AqualinkSensor`, canonical key `lvh1`) and `TcxHeaterEnableSwitch` (`AqualinkSwitch`, synthetic key `lvh1_enable`), both built from the same `reported["lvh1"]` dict in `_update_devices()` — the same synthetic-sibling technique already used for `ecm0`/`ecm0_manSpd` etc.

This mirrors `iaqua`'s existing pattern exactly: `IaquaClimate` is a pure façade over three *separate* sibling devices (`{type}_set_point`/`{type}_heater`/`{type}_temp`) and heater-equipment enable/status lives in its own `IaquaHeater`/`IaquaHeatPumpStatusSensor` devices, never inside the Climate entity. `lvh1` has no setpoint field of its own (`TspBdy0.waterTempSet` is the only setpoint on tcx), so it structurally can't be a `Climate` — it's the tcx analog of `IaquaHeater`/`IaquaHeatPumpStatusSensor`, sitting beside the existing `TcxClimate` (which owns `TspBdy0`).

`lvh1.en` is a *ranged* code (`0` → off, `1`–`5` → standby, `6` → heating, `≥7` → off), not a 1:1 wire code — `_lvh1_en_to_status()` (`src/iaqualink/systems/tcx/device.py`) classifies it directly into `"off"`/`"standby"`/`"heating"`, rather than using `AqualinkSensor.value_enum` (which does an exact-membership `cls(value)` lookup, e.g. `IaquaHeatPumpStatusSensor`'s pattern — doesn't fit a range).

`TcxHeaterEnableSwitch.is_on` reads `lvh1.app == "HEAT"`; `turn_on`/`turn_off` call the new `set_lvh_app_type(enabled)` (`"setLvhAppType"`, `NAMESPACE_TCX`) — a separate wire path from `TcxClimate.turn_on`/`turn_off`, which calls `set_heat_enabled` against `TspBdy0.heatEnabled`. Both toggle "is the heater enabled" from the user's perspective but through different shadow objects; neither has been observed live to confirm whether they're kept in sync by the controller or are independent.

### Aux light control (`TcxAuxLight`)

`aux0`…`auxN` entries are split by `aux[N].et` (`LightType` enum): `JL`/`IB`/`PSS`/`HU` (real color lights) dispatch to `TcxAuxLight` (`AqualinkLight`); `WL` (white light, non-color) and anything without `et` stay `TcxAuxSwitch`. `LightType` already existed in `enums.py`, unused, before this change.

`TcxAuxLight.is_on`/`turn_on`/`turn_off` reuse the existing, already-confirmed `set_aux(name, state)` (`aux0.st`) — same mechanism as `TcxAuxSwitch`. Color control is intentionally **raw-index only**: `current_color_index` (`currClr`), `set_color_index()` (new `set_aux_light`, `"setAuxLight"`, `{name: {"cmdClr": index}}`), `reset_color()` (new `reset_aux_light`, `"setAuxResetColor"`, `{name: {}}` — no confirmed extra fields). No `effect`/`effect_list` (named colors) are populated: `iaqua` has per-brand effect-name dicts (`IaquaColorLightJC`/`SL`/`CL`/`JL`/`IB`), but those are keyed on iaqua's own `subtype` codes on a different platform, and TCX's `HU` ("Hayward Universal ColorLogic") has no iaqua equivalent at all (iaqua's `CL` is a *Pentair* product of a similar name) — reusing those name lists across vendors without wire confirmation risks recording wrong color names as fact. Raw index control is the honest baseline; named effects can follow once a TCX-specific index→name mapping is wire-confirmed.

### Aux freeze protect (`TcxAuxFreezeProtectSwitch`)

Scoped to **aux0 only**, not generic across `aux[N]`. The wire action name is `setIsAux0FreezeProtect` — unlike the genuinely generic per-aux actions (`setAuxState`, `setAuxLight`, `setAuxResetColor`, `setAuxSetup`, all of which take whichever aux key is in the payload), this one has `"Aux0"` baked directly into the action name itself, indicating freeze protect is a real hardware feature of the aux0 relay specifically, not a capability every auxN has.

When `reported.aux0.fp` is present, `_update_devices()` registers a fixed synthetic `aux0_fp` key dispatched to `TcxAuxFreezeProtectSwitch` (`AqualinkSwitch`) — same singleton-sibling technique as `lvh1`/`lvh1_enable` above (fixed key, not name-derived). `is_on` reads `fp`; `turn_on`/`turn_off` call `set_aux_freeze_protect(enabled)` (`"setIsAux0FreezeProtect"`, `NAMESPACE_TCX`, `{"aux0": {"fp": enabled}}`) — no aux-name parameter, since the target is always aux0. `fp` present on any other `aux[N]` is intentionally ignored.

### Aux setup (`set_aux_setup`)

`setAuxSetup` is exposed as a plain `TcxSystem.set_aux_setup(name, *, app, et, ty, fr)` method with **no corresponding device entity** — consistent with the rest of this codebase, where no other `*Setup`-style action (e.g. `setFeatureCircuitSetup`) is modeled as an HA entity; configuration writes are administrative, not toggleable state. The field set (`app`/`et`/`ty`/`fr`) matches the one documented payload example available for this action.

### `AuxType` (`aux0.ty`)

Added to `enums.py` and the protocol reference's Enum Wire Values section. Not used for `TcxAuxLight`/`TcxAuxSwitch` dispatch — `et` (`LightType`) already disambiguates lights from non-lights and was already established in this codebase before this change. `ty` is only used cosmetically, for `TcxAuxSwitch.model` (e.g. `"Pump"`, `"Relay"`) when present. Unlike the rest of this reference doc, `AuxType`'s wire values were supplied via external protocol research rather than this repo's own decompiled-source/live-capture pipeline — flagged as not independently confirmed.

### Freeze-protection set point (`TcxFreezeSetPoint`)

Top-level `freezeSP` ("Freeze protection set point") is modeled as an `AqualinkNumber`, writable via the confirmed `setFreezeSetPoint` action (`NAMESPACE_TCX`). `freezeSP` isn't nested under any device object in `state.reported` — `set_freeze_set_point`'s delta mirrors that flat shape (`{"freezeSP": temp}`, not wrapped in a device key like `TspBdy0.waterTempSet`).

A sibling top-level field, `lowAirSP` ("Low air temperature threshold"), is unambiguously an *air*-temperature reading by name but has no documented write action — `setFreezeSetPoint` maps to `freezeSP` by the same 1:1 action-name-to-field-name convention this implementation already relies on elsewhere (`setWaterTempSetpoint` → `waterTempSet`, `setLvhAppType` → `lvh1.app`). `freezeSP`'s own live-captured example value (`33` raw → `3.3°C`) is close enough to freezing to support it being the real freeze-protection threshold, whatever sensor it's actually keyed off; `lowAirSP` is deliberately left unmodeled — user-scoped decision, not a confidence gap.

Same tenths-of-a-degree wire scaling as `waterTempSet`/`water.value`/`solar.value` (`_wire_temp_to_display`/`_display_temp_to_wire`), and the same whole-degree step convention as `TcxClimate.target_temperature` (the wire stores tenths; the public API only accepts whole degrees). Bounds (`_FREEZE_SP_MIN/MAX_F/_C` in `device.py`) are `34–42°F` (`1–6°C`), per a user-supplied device spec (`60–104°F`/`34–42°F`, `1°F` step, for water/solar/freeze-protection set points respectively) — see "Heater/solar min/max set-point" below for the shared water/solar bounds.

### Solar heater set point (`TcxSolarSetPoint`)

`TspBdy0.solarTempSet` is modeled as a synthetic sibling of `TcxClimate` — same technique as `lvh1`/`lvh1_enable`, built from the same `TspBdy0` dict under a synthetic key (`TspBdy0_solar`) rather than folded into the Climate entity itself (`AqualinkClimate` only has one `target_temperature`; a body with both water and solar heat sources needs two independent setpoints). Writable via the confirmed `setSolarTempSetpoint` action, same field-name convention as `setWaterTempSetpoint` → `waterTempSet`. Shares `TcxClimate`'s bounds (`_TEMP_SETPOINT_MIN/MAX_F/_C`) and tenths-of-a-degree scaling.

### Heater/solar min/max set-point

`TspBdy0` does not include explicit set-point bounds in the observed shadow schema, for either `waterTempSet` or `solarTempSet`. The implementation uses hardcoded defaults — `60–104°F` (`16–40°C`), `1°F` step — per a user-supplied device spec, shared by `TcxClimate.min_temp`/`max_temp` and `TcxSolarSetPoint.min_value`/`max_value` (`_TEMP_SETPOINT_MIN/MAX_F/_C` in `device.py`). Celsius bounds are the Fahrenheit values converted and rounded to the nearest whole degree (`60°F=15.56°C→16`, `104°F=40.00°C→40`), not independently specified. If the shadow includes bounds in practice, this should be updated to read them from the data.

### VSP speed commands

`ecm0.cmdSpd` (commanded speed RPM) is the write target. The `spdList` entries expose named presets. The percentage API maps linearly between `ecm0.minSpd` and `ecm0.maxSpd`.

### Speed sensors (`TcxSpeedSensor`)

Live wire capture shows `filt0` and `ecm0` both carry raw speed (RPM) fields beyond what `TcxVariableSpeedPump` already surfaces via `percentage`/`preset_mode`: `filt0.manSpd`, `ecm0.manSpd`, `ecm0.frzSpd` (freeze-protect), `ecm0.prmSpd` (priming), `ecm0.qcSpd` (quick-clean). These are exposed as standalone read-only `TcxSpeedSensor` devices, synthesized in `_update_devices()` under synthetic keys (`filt0_manSpd`, `ecm0_manSpd`, etc.) — not real wire device names, so `TcxDevice.from_data()` dispatches them by exact match against `_SPEED_SENSOR_NAMES` rather than the `filt0`/`ecm0` name branches.

`filt0.manSpd` and `ecm0.manSpd` are **not duplicates** — live-confirmed distinct values (`2000` vs `1900` on the same real system) — so both get separate sensors rather than being merged into one. `minSpd`/`maxSpd`/`cmdSpd`/`reqSpd` are deliberately **not** duplicated as standalone sensors: `minSpd`/`maxSpd` are identical between `filt0` and `ecm0` on real hardware and already back `TcxVariableSpeedPump.percentage`'s linear mapping; `cmdSpd` already backs `percentage`/`preset_mode`; `reqSpd` is a near-duplicate of `cmdSpd`.

No new write path was added — the Filtration namespace's only documented action is `setFilterPumpState` (on/off); VSP namespace actions exist for `setMinMasterSpeed`/`setMaxMasterSpeed`/`setPrimingSpeed`/`setQuickCleanSpeed`/`setFreezeProtectSpeed` (VSP *configuration*, not "run at this speed now" — distinct from `cmdSpd`'s live speed selection, already covered by `set_vsp_speed`/`_set_preset_mode`), but wiring writes for these wasn't requested and hasn't been wire-verified against real hardware.

### SWC device modelling

The SWC chlorinator is modelled as a boost on/off switch (`TcxChlorinatorBoost`) rather than a richer device. The output percentage (`outputPcnt`) and salinity are not yet surfaced as separate sensor devices.

## Deltas vs Protocol Reference

| # | Delta | Reason |
|---|---|---|
| 1 | SWC exposes boost only | Richer SWC surface (output %, salinity, mode) is future work |
| 2 | Heater/solar bounds hardcoded (`60–104°F`/`16–40°C`, shared by `TcxClimate` and `TcxSolarSetPoint`) | Shadow bounds field presence not confirmed. Values are per a user-supplied device spec rather than a guess; Celsius bounds are still a rounded Fahrenheit conversion, not independently specified |
| 3 | ~~ZigBee write payload shape unverified~~ — **resolved** | `set_zigbee_state` now posts `{name: {"st": N}}` (i.e. `{"auxz0": {"st": N}}`), confirmed via protocol research against the `_zig` sub-shadow's write shape (`{"state":{"desired":{"auxz0":{"st":1}}}}`) — see protocol reference's "ZigBee" command reference |
| 4 | REST sub-shadow reads (`_filt`, `_ecm`, `_fea`, `_zig`, `_sched`, `_pib0`, `_scene`) removed entirely — no longer fetched | Confirmed non-functional against real hardware — direct live probe of all 7 sub-shadow URLs returns `401 Unauthorized`; previously the "REST requests for all subsystems" behavior that motivated this change. Feature-circuit/ZigBee discovery now runs against the unified reported tree assembled from the WS Authorization payload instead (see "Feature-circuit / ZigBee discovery" above); `filt0`/`ecm0` field enrichment from `_filt`/`_ecm` has no replacement |
| 5 | ~~WS Authorization-ack payload shape assumed to mirror REST's flat `state.reported` envelope~~ — **resolved**: confirmed namespace-keyed on real hardware (see "WebSocket-primary reads and writes" above); `StateStreamer`/`DataStreamer`/`EventStreamer` delta payload shape is still unconfirmed (no delta observed live yet) | Full-state shape confirmed via live wire capture; delta shape remains inferred — `_reported_from_payload()` defensively supports both a flat and a namespace-keyed payload so either resolves correctly once confirmed |
| 6a | Feature-circuit key pattern (`feaCircuit[N]`) is unconfirmed against real hardware | Live wire capture from one real tcx unit shows a *different* shape: feature circuits use key `fcr[N]` (not `feaCircuit[N]`). `_parse_fea_sub_shadow` has not yet been updated to match; feature circuits will not be discovered on hardware matching this shape until it is. Separately-scoped gap, deliberately left unfixed alongside the ZigBee fix in 6b |
| 6b | ~~ZigBee device location (`zig` dict keyed by address) unconfirmed against real hardware~~ — **resolved** | Live wire capture confirmed the real shape: the ZigBee radio's own status lives at top-level `zig` (scalar fields, not a dict of devices) while attached ZigBee devices appear as separate top-level `auxz[N]` keys — analogous to `aux[N]`. `_parse_zig_sub_shadow`/`TcxZigbeeSwitch`/`set_zigbee_state` updated to match; see "Feature-circuit / ZigBee discovery" above |
| 7 | Per-action WS command payload shapes inferred by reusing each write method's existing REST desired-state delta (e.g. `{"filt0": {"st": state}}`) as the frame's `payload`, plus `clientToken` | The reference doc documents the command envelope but not field-level payloads per action; this is the only confirmed field-naming source available |
| 8 | `set_vsp_speed` uses the generic `tcx` namespace `"setState"` action | No documented VSP namespace action matches "set current commanded speed" (`cmdSpd`) — the other VSP actions are all specific-purpose (priming/min/max/quick-clean/freeze speeds) |
| 9 | Air sensor synthesized from `airTemp`/`airSnsr` scalar fields (per reference doc field table) | Live wire capture shows real hardware doesn't emit top-level `airTemp`/`airSnsr` at all — the air reading arrives as a full `air: {..., value, us}` object (same shape as `water`/`solar`), plus a separate `hubAir`/`airSnsr` pair at the main-namespace level that isn't the same field. `_update_devices` has not yet been updated to handle the real `air` object shape; not fixed as part of the WS-envelope correction — flagged here as a known, separately-scoped gap alongside delta #6. When fixed, apply the same tenths-of-a-degree scaling as delta #10 |
| 10 | Temperature wire fields (`waterTempSet`, `water.value`, `solar.value`, `freezeSP`, `lowAirSP`) assumed to be whole degrees in the active unit | Live wire capture shows they're tenths of a degree instead — confirmed by `freezeSP=33`/`lowAirSP=128` only making sense as `3.3`/`12.8`, and `waterTempSet`/`water.value` agreeing at raw `283` only making sense as `28.3°C`. Fixed for water/solar sensors and climate current/target temperature (read and write); `freezeSP`/`lowAirSP` aren't surfaced as device fields today so needed no code change |
| 11 | `pool` object (`et: "V_POS"`, `app: "POOL_M"`, live-observed alongside `filt0`/`ecm0` in the `filt` namespace) not parsed into any device | Semantics not confirmed (valve position indicator vs. something else); out of scope for the speed-sensor pass that added `TcxSpeedSensor` — deliberately deferred, not an oversight |
| 12 | `jva1`/`jva2` write path (`NAMESPACE_PIB`/`"setJvaState"`) is inferred, never wire-confirmed | No "PIB" command entries exist in the reference doc despite "PIB" being a listed namespace. Same inference precedent as `set_vsp_speed` (delta #8). Not exercised against real hardware — covered by mocked tests only |
| 13 | `pib0`'s own board-identity metadata (`sn`/`vr`/`pibConfig`/`app`) intentionally not modeled as a device | Consistent with the earlier decision not to model the `zig` namespace's own radio-metadata block as a device — only individually attached sub-devices become entities |
| 14 | `spare` (live-observed alongside `jva1`/`water`/`solar`/`air`/`aux0` in the `pib0` namespace) intentionally left entirely unparsed | Not confirmed to be in active use on any observed hardware (live value is a `-1311` sentinel with an undocumented `us=0` status); the reference doc has only a one-line stub for it, no confirmed sub-object schema |
| 15 | `set_lvh_app_type`/`set_aux_light`/`reset_aux_light`/`set_aux_setup`/`set_aux_freeze_protect` payload shapes inferred by reusing the same "wire field name -> desired-state delta" convention as delta #7 | Action names (`setLvhAppType`/`setAuxLight`/`setAuxResetColor`/`setAuxSetup`/`setIsAux0FreezeProtect`) and their namespace (`tcx`/`NAMESPACE_TCX`) are confirmed from the Command Reference table; no field-level payload example exists for any of the five. `reset_aux_light`'s delta is an empty `{name: {}}` — no confirmed extra fields. `set_aux_freeze_protect(enabled)` takes no aux-name parameter — target is hardcoded to `aux0`, matching the action name itself (see "Aux freeze protect" above) |
| 16 | `TcxAuxLight` exposes raw `currClr`/`cmdClr` color-index control only, no named `effect`/`effect_list` | No TCX-specific color-index-to-name mapping is wire-confirmed; iaqua's per-brand effect-name dicts are keyed on a different platform's codes and can't be safely assumed to match (see "Aux light control" above) |
| 17 | `AuxType` (`aux0.ty`) enum values supplied via external protocol research, not this repo's own decompiled-source/live-capture pipeline | Source doesn't match the confidence level of the rest of this reference doc; not used for dispatch (see "`AuxType`" above), cosmetic use only |
| 18 | `set_freeze_set_point`'s flat `{"freezeSP": temp}` payload shape inferred by the same convention as delta #7/#15 | Action name (`setFreezeSetPoint`) and namespace (`tcx`) are confirmed; no field-level payload example exists. Unlike every other write in this file, `freezeSP` isn't nested under a device key on read, so the delta isn't either |
| 19 | `freezeSP` assumed to be the freeze-protection threshold that `setFreezeSetPoint` writes, rather than the sibling `lowAirSP` field | User-scoped decision (see "Freeze-protection set point" above) — `setFreezeSetPoint`'s name matches `freezeSP` by this codebase's established action-name-to-field-name convention; `lowAirSP` has no documented write action at all and is left unmodeled |
| 20 | `TcxFreezeSetPoint` min/max bounds (`_FREEZE_SP_MIN/MAX_F/_C`, `34–42°F`/`1–6°C`) hardcoded | Shadow bounds field presence not confirmed — same caveat as delta #2 (heater/solar bounds), also per the same user-supplied device spec |
| 21 | `set_solar_temp_setpoint`'s `{"TspBdy0": {"solarTempSet": temp}}` payload shape inferred by the same convention as `set_water_temp_setpoint` | Action name (`setSolarTempSetpoint`) and namespace (`tcx`) are confirmed from the Command Reference table; no field-level payload example exists, same caveat as delta #7 |
