# Cyclobat Implementation Notes

Implementation details for cyclobat systems (`device_type: "cyclobat"` — Zodiac battery-powered robot cleaners). For the wire-level protocol, see [Protocol Reference: cyclobat](../../reference/systems/cyclobat.md).

## Overview

| Property | Value |
|----------|-------|
| `device_type` | `cyclobat` |
| API host | `prod.zodiac-io.com` |
| Authentication | JWT `IdToken` (bare, no `Bearer` prefix) |
| Update call | Single shadow state fetch (`GET /devices/v1/{serial}/shadow`) |
| Write commands | WebSocket `wss://prod-socket.zodiac-io.com/devices` via shared `_robot_ws` |
| Python class | `CyclobatSystem` in `src/iaqualink/systems/cyclobat/system.py` |

## System Status Lifecycle

Status is derived from the shadow response and request outcome, not from a wire field.

### `_refresh()` template

1. Issue `GET /devices/v1/{serial}/shadow` with `Authorization: {id_token}`.
2. Call `_parse_shadow_response()`:
   - Deserialise JSON; extract `state.reported`.
   - Traverse to `state.reported.equipment.robot`.
   - If `state.reported` is absent/malformed **or** `equipment.robot` is not a dict → raise `_AqualinkOfflineSignal`.
3. Flatten robot sub-keys into the device registry (see §Device Model below).
4. On success set `self.status = SystemStatus.ONLINE`.

### Status mapping

| Condition | `SystemStatus` |
|-----------|----------------|
| Shadow parsed successfully | `ONLINE` |
| `state.reported` absent or malformed | `OFFLINE` (base class handles `_AqualinkOfflineSignal`) |
| `equipment.robot` key missing or not a dict | `OFFLINE` |
| Network / HTTP error (non-401, non-429) | `DISCONNECTED` |
| HTTP 429 (throttled) | `UNKNOWN` |
| HTTP 401 → token refreshed → retry succeeds | `ONLINE` |

`refresh()` in the base class resets status to `IN_PROGRESS` before calling `_refresh()`.

## Device Model

All devices share a single flat data dict keyed by device name. Any `update()` call refreshes all device values atomically, since the full shadow is fetched and re-parsed each cycle.

### Device registry — flat keys emitted by `_parse_shadow_response`

Source sub-objects are flattened into underscored key names.

| Device key | Source path | Class |
|---|---|---|
| `main_state` | `main.state` | `CyclobatSensor` |
| `main_ctrl` | `main.ctrl` | `CyclobatSensor` |
| `main_mode` | `main.mode` | `CyclobatSensor` |
| `main_error` | `main.error` | `CyclobatSensor` |
| `main_cycleStartTime` | `main.cycleStartTime` | `CyclobatSensor` |
| `battery_state` | `battery.state` | `CyclobatSensor` |
| `battery_percentage` | `battery.userChargePerc` | `CyclobatSensor` |
| `battery_charge_state` | `battery.userChargeState` | `CyclobatSensor` |
| `battery_cycles` | `battery.cycles` | `CyclobatSensor` |
| `battery_warning_code` | `battery.warning.code` | `CyclobatSensor` |
| `battery_version` | `battery.vr` | `CyclobatSensor` |
| `total_runtime` | `stats.totRunTime` | `CyclobatSensor` |
| `diagnostic_code` | `stats.diagnostic` | `CyclobatSensor` |
| `temperature` | `stats.tmp` | `CyclobatSensor` |
| `last_error_code` | `stats.lastError.code` | `CyclobatSensor` |
| `last_error_cycle` | `stats.lastError.cycleNb` | `CyclobatSensor` |
| `last_cycle_number` | `lastCycle.cycleNb` | `CyclobatSensor` |
| `last_cycle_duration` | `lastCycle.duration` | `CyclobatSensor` |
| `last_cycle_mode` | `lastCycle.mode` | `CyclobatSensor` |
| `cycle` | `lastCycle.endCycleType` | `CyclobatSensor` |
| `last_cycle_error` | `lastCycle.errorCode` | `CyclobatSensor` |
| `floor_duration` | `cycles.floorTim.duration` | `CyclobatSensor` |
| `floor_walls_duration` | `cycles.floorWallsTim.duration` | `CyclobatSensor` |
| `smart_duration` | `cycles.smartTim.duration` | `CyclobatSensor` |
| `waterline_duration` | `cycles.waterlineTim.duration` | `CyclobatSensor` |
| `first_smart_done` | `cycles.firstSmartDone` | `CyclobatSensor` |
| `lift_pattern_time` | `cycles.liftPatternTim` | `CyclobatSensor` |
| `vr` | `vr` | `CyclobatSensor` |
| `sn` | `sn` | `CyclobatSensor` |
| `model_number` | `modelNumber` | `CyclobatSensor` |
| `running` | derived from `main.state == 1` | `CyclobatBinarySensor` |
| `returning` | derived from `main.state == 3` | `CyclobatBinarySensor` |
| `time_remaining_sec` | derived (see below) | `CyclobatSensor` |

### Derived values

**`running`** — `True` when `main.state == CYCLOBAT_STATE_CLEANING` (1).

**`returning`** — `True` when `main.state == CYCLOBAT_STATE_RETURNING` (3).

**`time_remaining_sec`** — computed as:
`main.cycleStartTime + cycles[lastCycle.endCycleType].duration * 60 - time.time()`, clamped to 0. Returns `None` if any input field is absent or the cycle index is out of range.

## Write Path

All write commands go through the shared WebSocket `_robot_ws` (`CyclobatWs`), not the shadow REST endpoint. `send_set_ctrl(ws, serial, id_token, ctrl)` builds and sends a `setCleaningMode` frame with the target `ctrl` value.

| Method | ctrl value | Meaning |
|---|---|---|
| `start_cleaning()` | 1 | Start cleaning cycle |
| `stop_cleaning()` | 0 | Stop |
| `return_to_base()` | 3 | Return to base / dock |

## Design Decisions

### Read path is HTTP shadow GET; write path is WebSocket

The reference app uses WebSocket for both reads and writes. The Python implementation polls the HTTP REST shadow endpoint for reads (same pattern as the eXO implementation) and uses the WebSocket only for write commands. This avoids managing a persistent connection for polling.

### Device registry flattened into underscored keys

Nested shadow sub-objects (`main`, `battery`, `stats`, `lastCycle`, `cycles`) are flattened at parse time into a single dict keyed by underscore-joined names. This mirrors the i2d pattern and keeps device access uniform across system types.

### `time_remaining_sec` derived at parse time

Time remaining is not a wire field. It is computed from `cycleStartTime`, the cycle duration table, and the wall clock at parse time. It is not recomputed between refreshes.

## Deltas vs Protocol Reference

None at present.

## See Also

- [Protocol Reference: cyclobat](../../reference/systems/cyclobat.md) — wire-level spec
- [API Reference: cyclobat](../../api/systems/cyclobat.md) — class and method docs
