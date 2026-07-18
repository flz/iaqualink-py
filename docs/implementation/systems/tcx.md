# TCX Implementation Notes

Implementation details for the TCX system (`device_type: "tcx"`). For the wire-level protocol, see [Protocol Reference: TCX](../../reference/systems/tcx.md).

## Overview

| Property | Value |
|----------|-------|
| `device_type` | `tcx` |
| API host | `prod.zodiac-io.com` (REST), `prod-socket.zodiac-io.com` (WS) |
| Authentication | JWT `IdToken` (Bearer on REST; bare on WS) |
| Update call | WS state subscription (primary); main shadow (`GET /devices/v2/{serial}/shadow`) + active sub-shadows as a one-shot bootstrap/fallback |
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

### From sub-shadows

Sub-shadows are fetched concurrently after the main shadow on each `_refresh()` call. Presence is discovered from `state.reported.equipment` keys.

| Sub-shadow | Action | New devices |
|---|---|---|
| `_filt` | Merges `state.reported` into `filt0` device data | None (enriches existing) |
| `_ecm` | Merges `state.reported` into `ecm0` device data | None (enriches existing) |
| `_fea` | Discovers feature circuits | `TcxFeatureCircuit` (one per `feaCircuit[N]` key) |
| `_zig` | Discovers ZigBee devices | `TcxZigbeeSwitch` (one per device in `zig` dict) |
| `_sched` | Fetched but not parsed | None |
| `_pib0` | Fetched but not parsed | None |
| `_scene` | Fetched but not parsed | None |

Sub-shadow failures are isolated — a failed fetch for one suffix does not abort others. The failure is logged at WARNING level and the refresh continues.

## Design Decisions

### WebSocket-primary reads and writes

Per the reference app, REST shadow GET is only a one-shot online/offline status check on the system list screen — it is not part of the live data flow, and commands are issued over WebSocket. `TcxSystem` mixes in `TcxStateSubscription` (`src/iaqualink/systems/tcx/ws.py`), built on the shared `WsStateSubscription` engine (`src/iaqualink/utils/websockets.py`, also used by `cyclobat`'s `RobotStateSubscription`):

- `_refresh()` skips the REST fetch while `_ws_state_fresh()` is true. It does **not** call `start_ws_subscription()` itself — the library must not spin up background tasks on its own; a consumer (CLI/HA) opts in by calling it explicitly. Until a consumer does, `_refresh()` behaves exactly as before (a plain REST poll every call).
- All 8 write methods (`set_filter_pump`, `set_aux`, `set_heat_enabled`, `set_water_temp_setpoint`, `set_swc_boost`, `set_vsp_speed`, `set_feature_circuit_state`, `set_zigbee_state`) send WS `StateController` command frames (`service`/`namespace`/`action`/`target`/`payload`) instead of REST POST. Writes are fire-and-forget (best-effort ack, no synchronous error) — wire-level errors are signaled asynchronously via `ErrorStreamer`, not yet wired into an exception on the calling command.
- `start_ws_subscription()`/`stop_ws_subscription()` are provided but not auto-invoked by any consumer (same as cyclobat) — wiring into CLI/HA is separate future work.

Unlike cyclobat, tcx has no "robot" wrapper concept in its shadow — the reported tree is flat and multi-key across ~9 namespaces (see the protocol reference) — so `TcxStateSubscription` implements the generic engine's hooks directly against the whole reported tree rather than drilling into a sub-object.

**Unconfirmed assumptions** (see Deltas table below): the WS ack/delta payload's inner shape beyond the envelope, and per-action WS command payload field shapes — the reference doc only documents the envelope, not field-level bodies.

### Shadow URL versions

TCX main shadow reads use `/devices/v2/` (spec §Shadow Endpoints). Sub-shadow reads use `/devices/v1/` with the suffixed serial. All writes (main and sub-shadow) use `/devices/v2/`.

### Concurrent sub-shadow fetch

Sub-shadows are fetched with `asyncio.gather(..., return_exceptions=True)`. Each failure is logged individually rather than aborting the whole refresh. This tolerates temporary sub-shadow unavailability without marking the system offline.

### HMAC signature on main shadow GET

The main shadow GET (`/devices/v2/{serial}/shadow`) requires `?signature={sig}` or the request is rejected with `400 BAD_REQUEST` (`"missing signature"`). `sig` is `sign([serial.upper(), user_id], AQUALINK_API_SIGNING_KEY)` — the same HMAC-SHA1 helper and signing key used for device discovery, with `[serial.upper(), user_id]` as the message parts. Sub-shadow GETs (`/devices/v1/`) and all writes (`POST`) do not require a signature.

### Temperature unit

`state.reported.tempSetting` encodes unit: `0` = °C, `1` = °F. The implementation reads this field and stores it on `TcxSystem.temp_unit`. Default is `"F"` if the field is absent.

### Heater min/max set-point

`TspBdy0` does not include explicit set-point bounds in the initial observed shadow schema. The implementation uses hardcoded defaults (`65–104°F`, `18–40°C`) matching typical pool heater ranges. If the shadow includes bounds in practice, this should be updated to read them from the data.

### VSP speed commands

`ecm0.cmdSpd` (commanded speed RPM) is the write target. The `spdList` entries expose named presets. The percentage API maps linearly between `ecm0.minSpd` and `ecm0.maxSpd`.

### SWC device modelling

The SWC chlorinator is modelled as a boost on/off switch (`TcxChlorinatorBoost`) rather than a richer device. The output percentage (`outputPcnt`) and salinity are not yet surfaced as separate sensor devices.

## Deltas vs Protocol Reference

| # | Delta | Reason |
|---|---|---|
| 1 | SWC exposes boost only | Richer SWC surface (output %, salinity, mode) is future work |
| 2 | Heater bounds hardcoded | Shadow bounds field presence not confirmed |
| 3 | ZigBee write payload shape unverified | `set_zigbee_state` posts `{"zig": {addr: {"st": N}}}`; not confirmed from wire traffic |
| 4 | `_sched`, `_pib0`, `_scene` fetched but not parsed | Schema not confirmed; no device mapping defined yet |
| 5 | WS Authorization-ack/StateStreamer-delta payload shape assumed to mirror REST's `state.reported` envelope, with no `robot`-style nesting level | Only the outer frame envelope (`service`/`target`/`namespace`/`payload`) is confirmed in the reference doc; the payload's inner structure has no confirmed example |
| 6 | Sub-shadow-namespace-scoped WS deltas (e.g. `filtration` carrying `{"filt0": {...}}`) assumed to arrive in the same flat envelope and applied via the same generic per-key merge, without namespace-specific parsing | Even less confirmed than the main-namespace shape; mechanically safe due to `_update_devices`'s per-key guards, but unverified on the wire |
| 7 | Per-action WS command payload shapes inferred by reusing each write method's existing REST desired-state delta (e.g. `{"filt0": {"st": state}}`) as the frame's `payload`, plus `clientToken` | The reference doc documents the command envelope but not field-level payloads per action; this is the only confirmed field-naming source available |
| 8 | `set_vsp_speed` uses the generic `tcx` namespace `"setState"` action | No documented VSP namespace action matches "set current commanded speed" (`cmdSpd`) — the other VSP actions are all specific-purpose (priming/min/max/quick-clean/freeze speeds) |
