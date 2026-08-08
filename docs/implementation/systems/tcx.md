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
| `aux0`…`auxN` | `TcxAuxSwitch` | `AqualinkSwitch` | Discovered dynamically by key pattern `aux[0-9]+` |
| `TspBdy0` | `TcxClimate` | `AqualinkClimate` | Uppercase T — wire-level invariant |
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
- All 8 write methods (`set_filter_pump`, `set_aux`, `set_heat_enabled`, `set_water_temp_setpoint`, `set_swc_boost`, `set_vsp_speed`, `set_feature_circuit_state`, `set_zigbee_state`) send WS `StateController` command frames (`service`/`namespace`/`action`/`target`/`payload`) instead of REST POST. Writes are fire-and-forget (best-effort ack, no synchronous error) — wire-level errors are signaled asynchronously via `ErrorStreamer`, not yet wired into an exception on the calling command.

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

### Heater min/max set-point

`TspBdy0` does not include explicit set-point bounds in the initial observed shadow schema. The implementation uses hardcoded defaults (`65–104°F`, `18–40°C`) matching typical pool heater ranges. If the shadow includes bounds in practice, this should be updated to read them from the data.

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
| 2 | Heater bounds hardcoded | Shadow bounds field presence not confirmed |
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
