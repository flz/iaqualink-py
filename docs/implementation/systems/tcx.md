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

### Feature-circuit / ZigBee discovery (best-effort, WS-driven)

`TcxFeatureCircuit` (one per `feaCircuit[N]` key) and `TcxZigbeeSwitch` (one per device in a `zig` dict) used to be discovered from dedicated REST sub-shadow responses (`_fea`, `_zig`). That REST sub-shadow fetch (`/devices/v1/{serial}{suffix}/shadow`, one GET per active suffix reported under `state.reported.equipment`) is **confirmed non-functional against real hardware** and has been removed.

`_parse_fea_sub_shadow`/`_parse_zig_sub_shadow` now run unconditionally against whatever reported tree `_apply_reported_state` sees — the REST main shadow, a WS Authorization full-state ack, or a WS delta merged onto the cached tree. Both guard on their own key patterns (`feaCircuitN` prefix, `zig` dict), so this is a safe no-op when the data isn't present. This is a best-effort fallback, not a wire-confirmed behavior: whether the WS payload actually carries `feaCircuitN`/`zig` keys in the unified tree is unconfirmed (see Deltas table). If it doesn't, these devices simply won't appear until that's separately verified.

The `_filt`/`_ecm` sub-shadow responses used to additionally enrich `filt0`/`ecm0` device data with fields beyond what the main shadow's `reported.filt0`/`reported.ecm0` carries. That enrichment had no safe equivalent once the REST fetch was removed (the sub-shadow response's own document root *was* the flat filt0/ecm0 field set, a different shape than the nested `reported.filt0`/`reported.ecm0` the main shadow and `_update_devices()` use) and was dropped rather than reintroduced. `_update_devices()`'s existing handling of `reported.filt0`/`reported.ecm0` still picks up whatever fields land there via the main shadow or WS.

`_sched`, `_pib0`, `_scene` sub-shadows were fetched but never parsed into devices even before this change — no functionality is lost there.

## Design Decisions

### WebSocket-primary reads and writes

Per the reference app, REST shadow GET is only a one-shot online/offline status check on the system list screen — it is not part of the live data flow, and commands are issued over WebSocket. `TcxSystem` mixes in `TcxStateSubscription` (`src/iaqualink/systems/tcx/ws.py`), built on the shared `WsStateSubscription` engine (`src/iaqualink/utils/websockets.py`, also used by `cyclobat`'s `RobotStateSubscription`):

- `_refresh()` calls `_ws_refresh_gate()`, which auto-starts the WS subscription (idempotent — a no-op once a live task exists) and skips the REST fetch while `_ws_state_fresh()` is true. `AqualinkClient.close()` stops any subscriptions it auto-started (systems register themselves with the client on `start_ws_subscription()`), so a consumer that never calls `stop_ws_subscription()` itself doesn't leak a background task + connection.
- All 8 write methods (`set_filter_pump`, `set_aux`, `set_heat_enabled`, `set_water_temp_setpoint`, `set_swc_boost`, `set_vsp_speed`, `set_feature_circuit_state`, `set_zigbee_state`) send WS `StateController` command frames (`service`/`namespace`/`action`/`target`/`payload`) instead of REST POST. Writes are fire-and-forget (best-effort ack, no synchronous error) — wire-level errors are signaled asynchronously via `ErrorStreamer`, not yet wired into an exception on the calling command.

This start/stop lifecycle binding (tied to `_refresh()` calls and client close) is a library design choice, not observed from the reference app — no vendor evidence documents the reference app's actual WS session lifetime.

Unlike cyclobat, tcx has no "robot" wrapper concept in its shadow — the reported tree is flat and multi-key across ~9 namespaces (see the protocol reference) — so `TcxStateSubscription` implements the generic engine's hooks directly against the whole reported tree rather than drilling into a sub-object.

**Unconfirmed assumptions** (see Deltas table below): the WS ack/delta payload's inner shape beyond the envelope, and per-action WS command payload field shapes — the reference doc only documents the envelope, not field-level bodies.

### Shadow URL versions

TCX main shadow reads use `/devices/v2/` (spec §Shadow Endpoints). All writes use `/devices/v2/`. Sub-shadow reads (`/devices/v1/` with the suffixed serial) are no longer issued by this library — see "Feature-circuit / ZigBee discovery" above.

### HMAC signature on main shadow GET

The main shadow GET (`/devices/v2/{serial}/shadow`) requires `?signature={sig}` or the request is rejected with `400 BAD_REQUEST` (`"missing signature"`). `sig` is `sign([serial.upper(), user_id], AQUALINK_API_SIGNING_KEY)` — the same HMAC-SHA1 helper and signing key used for device discovery, with `[serial.upper(), user_id]` as the message parts. Writes (`POST`) do not require a signature.

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
| 4 | REST sub-shadow reads (`_filt`, `_ecm`, `_fea`, `_zig`, `_sched`, `_pib0`, `_scene`) removed entirely — no longer fetched | Confirmed non-functional against real hardware (field report); previously the "REST requests for all subsystems" behavior that motivated this change. Feature-circuit/ZigBee discovery now runs best-effort against the unified reported tree instead (see "Feature-circuit / ZigBee discovery" above); `filt0`/`ecm0` field enrichment from `_filt`/`_ecm` has no replacement |
| 5 | WS Authorization-ack/StateStreamer-delta payload shape assumed to mirror REST's `state.reported` envelope, with no `robot`-style nesting level | Only the outer frame envelope (`service`/`target`/`namespace`/`payload`) is confirmed in the reference doc; the payload's inner structure has no confirmed example |
| 6 | Sub-shadow-namespace-scoped WS deltas (e.g. `filtration` carrying `{"filt0": {...}}`, `featureCircuit` carrying `feaCircuitN` keys, `zigbee` carrying a `zig` dict) assumed to arrive in the same flat envelope and applied via the same generic per-key merge, without namespace-specific parsing | Even less confirmed than the main-namespace shape; mechanically safe due to `_update_devices`'s per-key guards and `_parse_fea_sub_shadow`/`_parse_zig_sub_shadow`'s own key-pattern guards, but unverified on the wire — if the WS payload nests this data differently, feature-circuit/ZigBee devices won't populate |
| 7 | Per-action WS command payload shapes inferred by reusing each write method's existing REST desired-state delta (e.g. `{"filt0": {"st": state}}`) as the frame's `payload`, plus `clientToken` | The reference doc documents the command envelope but not field-level payloads per action; this is the only confirmed field-naming source available |
| 8 | `set_vsp_speed` uses the generic `tcx` namespace `"setState"` action | No documented VSP namespace action matches "set current commanded speed" (`cmdSpd`) — the other VSP actions are all specific-purpose (priming/min/max/quick-clean/freeze speeds) |
