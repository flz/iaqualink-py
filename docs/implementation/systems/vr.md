# VR Implementation Notes

Implementation details for VR systems (`device_type: "vr"` — Zodiac variable-speed robot pool cleaners). For the wire-level protocol, see [Protocol Reference: vr](../../reference/systems/vr.md).

## Overview

| Property | Value |
|----------|-------|
| `device_type` | `vr` |
| API host | `prod.zodiac-io.com` |
| Authentication | JWT `IdToken` (bare, no `Bearer` prefix) |
| Update call | Single shadow state fetch (`GET /devices/v1/{serial}/shadow`) |
| Write commands | WebSocket `wss://prod-socket.zodiac-io.com/devices` via `AqualinkClient.send_ws_frame` + shared `iaqualink.shared.robots` framing |
| Python class | `VrSystem` in `src/iaqualink/systems/vr/system.py` |

## System Status Lifecycle

Status is derived from the shadow response and request outcome, not from a wire field.

### `_refresh()` template

1. Issue `GET /devices/v1/{serial}/shadow` with `Authorization: {id_token}`.
2. Call `_parse_shadow_response()`:
   - Deserialise JSON; extract `state.reported`.
   - Traverse to `state.reported.equipment.robot` (a dict — not a list like cyclonext).
   - If `state.reported` is absent/malformed **or** `equipment.robot` is absent or not a dict → raise `_AqualinkOfflineSignal`.
3. Flatten robot fields into the device registry (see §Device Model below).
4. On success set `self.status = SystemStatus.ONLINE`.

### Status mapping

| Condition | `SystemStatus` |
|-----------|----------------|
| Shadow parsed successfully | `ONLINE` |
| `state.reported` absent or malformed | `OFFLINE` (base class handles `_AqualinkOfflineSignal`) |
| `equipment.robot` absent or not a dict | `OFFLINE` |
| Network / HTTP error (non-401, non-429) | `DISCONNECTED` |
| HTTP 429 (throttled) | `UNKNOWN` |
| HTTP 401 → token refreshed → retry succeeds | `ONLINE` |

`refresh()` in the base class resets status to `IN_PROGRESS` before calling `_refresh()`.

## Device Model

All devices share a single flat data dict keyed by device name. Any `update()` call refreshes all device values atomically, since the full shadow is fetched and re-parsed each cycle.

### Device registry — flat keys emitted by `_parse_shadow_response`

| Device key | Source path | Class |
|---|---|---|
| `state` | `robot.state` | `VrSensor` |
| `prCyc` | `robot.prCyc` | `VrSensor` |
| `stepper` | `robot.stepper` | `VrSensor` |
| `cycleStartTime` | `robot.cycleStartTime` | `VrSensor` |
| `sn` | `robot.sn` | `VrSensor` |
| `vr` | `robot.vr` | `VrSensor` |
| *(other scalar robot fields)* | `robot.<key>` (minus nested dicts) | `VrSensor` |
| `temperature` | `robot.sensors.sns_1.val` (fallback `.state`) | `VrSensor` |
| `model_number` | `devices.json id` | `VrSensor` |
| `running` | derived — `True` when `state == VR_STATE_CLEANING` (1) | `VrBinarySensor` |
| `returning` | derived — `True` when `state == VR_STATE_RETURNING` (3) | `VrBinarySensor` |
| `time_remaining_sec` | derived (see below) | `VrSensor` |

### Derived values

**`running`** — `True` when `state == VR_STATE_CLEANING` (1).

**`returning`** — `True` when `state == VR_STATE_RETURNING` (3).

**`time_remaining_sec`** — computed as:
`cycleStartTime + (durations[ordinal] + stepper) * 60 - time.time()`, clamped to 0. The duration is looked up by the **ordinal index** of `prCyc` into the sorted `durations` values list (vendor convention). Returns `None` if any input field is absent or the ordinal has no matching entry.

## Write Path

All write commands go through the shared WebSocket transport (`AqualinkClient.send_ws_frame`, frames built by `iaqualink.shared.robots`), not the shadow REST endpoint. Commands wrap their equipment state in `{"robot": {...}}` (literal `"robot"` key — no dot, unlike cyclonext's `"robot.1"`).

| Method | Equipment state | Meaning |
|---|---|---|
| `start_cleaning(cycle=None)` | set_cycle then `{"robot": {"state": 1}}` | Start cleaning (optionally sets cycle first) |
| `stop_cleaning()` | `{"robot": {"state": 0}}` | Stop cleaning |
| `pause_cleaning()` | `{"robot": {"state": 2}}` | Pause (required before remote control) |
| `return_to_base()` | `{"robot": {"state": 3}}` | Return robot to base |
| `set_cycle(cycle)` | `{"robot": {"prCyc": N}}` | `cycle` validated against `CYCLE_LABELS` |
| `set_runtime_extension(minutes)` | `{"robot": {"stepper": minutes}}` | Set absolute runtime extension |
| `adjust_runtime(delta_minutes)` | `{"robot": {"stepper": clamped}}` | Clamps current `stepper` at 0, sends absolute value |
| `remote_forward()` | `{"robot": {"rmt_ctrl": 1}}` | Remote control — forward |
| `remote_backward()` | `{"robot": {"rmt_ctrl": 2}}` | Remote control — backward |
| `remote_rotate_right()` | `{"robot": {"rmt_ctrl": 3}}` | Remote control — rotate right |
| `remote_rotate_left()` | `{"robot": {"rmt_ctrl": 4}}` | Remote control — rotate left |
| `remote_stop()` | `{"robot": {"rmt_ctrl": 0}}` | Remote control — stop movement |

## Design Decisions

### `robot` is a DICT (not a list)

The shadow response carries `equipment.robot` as a **dict** for VR systems. This differs from cyclonext where `equipment.robot` is a list. The parser checks `isinstance(robot, dict)` directly — no need to scan for the first dict entry.

### Duration lookup by ordinal index

The duration for `time_remaining_sec` is looked up by the **ordinal index** of `prCyc` into the sorted `durations` values list. This is a vendor convention where `durations` is an ordered dict and `prCyc` selects a cycle by its position in that ordering, not by a named key.

### `namespace: ClassVar[str] = "vr"` — reusable by VortraxSystem

`VrSystem` exposes a `namespace` class variable set to `"vr"`. `VortraxSystem` subclasses `VrSystem` and overrides `namespace = "vortrax"`, reusing the same shadow parser and write path with a different WebSocket namespace.

### Auto-pause before remote control

The vendor protocol requires the robot to be in `state == 2` (paused) before accepting `setRemoteSteeringControl` frames. `VrSystem` tracks remote mode via a `_remote_control_active` flag and automatically issues a `pause_cleaning()` call before the first remote command if the robot is not already paused.

## Deltas vs Protocol Reference

None at present.

## See Also

- [Protocol Reference: vr](../../reference/systems/vr.md) — wire-level spec
- [API Reference: vr](../../api/systems/vr.md) — class and method docs
