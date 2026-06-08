# TCX Implementation Notes

Implementation details for the TCX system (`device_type: "tcx"`). For the wire-level protocol, see [Protocol Reference: TCX](../../reference/systems/tcx.md).

## Overview

| Property | Value |
|----------|-------|
| `device_type` | `tcx` |
| API host | `prod.zodiac-io.com` |
| Authentication | JWT `IdToken` (Bearer) |
| Update call | Main shadow (`GET /devices/v2/{serial}/shadow`) + active sub-shadows |
| State updates | Desired/reported state pattern (`POST /devices/v2/{serial}/shadow`) |
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

### REST polling only (no WebSocket or MQTT)

The reference app uses WebSocket (server default) or MQTT for real-time push. The Python implementation polls the HTTP REST shadow endpoint (`GET /devices/v2/{serial}/shadow`), which exposes the same data. Desired state writes use the same REST endpoint.

This matches the EXO precedent and avoids persistent connection management.

### Shadow URL versions

TCX main shadow reads use `/devices/v2/` (spec §Shadow Endpoints). Sub-shadow reads use `/devices/v1/` with the suffixed serial. All writes (main and sub-shadow) use `/devices/v2/`.

### Concurrent sub-shadow fetch

Sub-shadows are fetched with `asyncio.gather(..., return_exceptions=True)`. Each failure is logged individually rather than aborting the whole refresh. This tolerates temporary sub-shadow unavailability without marking the system offline.

### HMAC signature on shadow GET

The reference spec notes `?signature={sig}` on shadow GET requests. The signing key and exact parameter list are not confirmed from the wire. The implementation omits the signature. If the endpoint rejects unsigned requests, the signature scheme can be added without a protocol change.

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
| 1 | Shadow GET omits `?signature={sig}` | Signing params unknown; endpoint may not require it |
| 2 | SWC exposes boost only | Richer SWC surface (output %, salinity, mode) is future work |
| 3 | Heater bounds hardcoded | Shadow bounds field presence not confirmed |
| 4 | ZigBee write payload shape unverified | `set_zigbee_state` posts `{"zig": {addr: {"st": N}}}`; not confirmed from wire traffic |
| 5 | `_sched`, `_pib0`, `_scene` fetched but not parsed | Schema not confirmed; no device mapping defined yet |
