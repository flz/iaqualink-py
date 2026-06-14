# Cyclonext Implementation Notes

Implementation details for cyclonext systems (`device_type: "cyclonext"` — Zodiac wired robot cleaners). For the wire-level protocol, see [Protocol Reference: cyclonext](../../reference/systems/cyclonext.md).

## Overview

| Property | Value |
|----------|-------|
| `device_type` | `cyclonext` |
| API host | `prod.zodiac-io.com` |
| Authentication | JWT `IdToken` (bare, no `Bearer` prefix) |
| Update call | Single shadow state fetch (`GET /devices/v1/{serial}/shadow`) |
| Write commands | WebSocket `wss://prod-socket.zodiac-io.com/devices` via `AqualinkClient.send_ws_frame` + shared `iaqualink.shared.robots` framing |
| Python class | `CyclonextSystem` in `src/iaqualink/systems/cyclonext/system.py` |

## System Status Lifecycle

Status is derived from the shadow response and request outcome, not from a wire field.

### `_refresh()` template

1. Issue `GET /devices/v1/{serial}/shadow` with `Authorization: {id_token}`.
2. Call `_parse_shadow_response()`:
   - Deserialise JSON; extract `state.reported`.
   - Traverse to `state.reported.equipment.robot` (a list).
   - Find the first dict entry in the list using `next((r for r in robot_list if isinstance(r, dict)), None)`.
   - If `state.reported` is absent/malformed **or** no dict entry is found in the robot list → raise `_AqualinkOfflineSignal`.
3. Flatten robot fields into the device registry (see §Device Model below).
4. On success set `self.status = SystemStatus.ONLINE`.

### Status mapping

| Condition | `SystemStatus` |
|-----------|----------------|
| Shadow parsed successfully | `ONLINE` |
| `state.reported` absent or malformed | `OFFLINE` (base class handles `_AqualinkOfflineSignal`) |
| `equipment.robot` list has no dict entry | `OFFLINE` |
| Network / HTTP error (non-401, non-429) | `DISCONNECTED` |
| HTTP 429 (throttled) | `UNKNOWN` |
| HTTP 401 → token refreshed → retry succeeds | `ONLINE` |

`refresh()` in the base class resets status to `IN_PROGRESS` before calling `_refresh()`.

## Device Model

All devices share a single flat data dict keyed by device name. Any `update()` call refreshes all device values atomically, since the full shadow is fetched and re-parsed each cycle.

### Device registry — flat keys emitted by `_parse_shadow_response`

| Device key | Source path | Class |
|---|---|---|
| `mode` | `robot[1].mode` | `CyclonextSensor` |
| `cycle` | `robot[1].cycle` | `CyclonextSensor` |
| `cycleStartTime` | `robot[1].cycleStartTime` | `CyclonextSensor` |
| `stepper` | `robot[1].stepper` | `CyclonextSensor` |
| `error_code` | `robot[1].errors.code` | `CyclonextErrorSensor` |
| `ebox_*` | `reported.eboxData.*` (each key prefixed) | `CyclonextSensor` |
| `control_box_vr` | `reported.vr` | `CyclonextSensor` |
| `model_number` | `devices.json id` | `CyclonextSensor` |
| `running` | derived from `mode != 0` | `CyclonextBinarySensor` |
| `time_remaining_sec` | derived (see below) | `CyclonextSensor` |

### Derived values

**`running`** — `True` when `mode != MODE_STOP` (0).

**`time_remaining_sec`** — computed as:
`cycleStartTime + durations[cycle_key] * 60 - time.time()`, clamped to 0. Returns `None` if any input field is absent or the cycle index has no matching duration key.

The cycle → duration key mapping is:

| `cycle` | `durations` key |
|---|---|
| 1 (floor) | `quickTim` |
| 3 (floor_and_walls) | `deepTim` |

## Write Path

All write commands go through the shared WebSocket transport (`AqualinkClient.send_ws_frame`, frames built by `iaqualink.shared.robots`), not the shadow REST endpoint. Commands wrap their equipment state in `{"robot.1": {...}}` (a literal string key with a dot — cyclonext-specific).

| Method | Equipment state | Meaning |
|---|---|---|
| `start_cleaning(cycle=None)` | set_cycle then `{"robot.1": {"mode": 1}}` | Start cleaning (optionally sets cycle first) |
| `stop_cleaning()` | `{"robot.1": {"mode": 0}}` | Stop (also exits Remote/Lift) |
| `pause_cleaning()` | `{"robot.1": {"mode": 2}}` | Alias for `MODE_REMOTE` (mode==2) |
| `set_runtime_extension(minutes)` | `{"robot.1": {"stepper": minutes}}` | `minutes` must be ≥0 and a multiple of 15 |
| `adjust_runtime(delta_minutes)` | `{"robot.1": {"stepper": clamped}}` | Clamps current `stepper` at 0, sends absolute value |
| `remote_forward()` | `{"robot.1": {"mode": 2, "direction": 1}}` | Remote control — forward |
| `remote_backward()` | `{"robot.1": {"mode": 2, "direction": 2}}` | Remote control — backward |
| `remote_rotate_left()` | `{"robot.1": {"mode": 2, "direction": 4}}` | Remote control — rotate left |
| `remote_rotate_right()` | `{"robot.1": {"mode": 2, "direction": 3}}` | Remote control — rotate right |
| `remote_stop()` | `{"robot.1": {"mode": 2, "direction": 0}}` | Remote control — stop movement |
| `lift_eject()` | `{"robot.1": {"mode": 3, "direction": 5}}` | Lift system — eject |
| `lift_rotate_left()` | `{"robot.1": {"mode": 3, "direction": 6}}` | Lift system — rotate left |
| `lift_rotate_right()` | `{"robot.1": {"mode": 3, "direction": 7}}` | Lift system — rotate right |
| `lift_stop()` | `{"robot.1": {"mode": 3, "direction": 0}}` | Lift system — stop |

## Design Decisions

### Robot payload at `equipment.robot[1]`

The shadow response carries `equipment.robot` as a list where index 0 is always null and the first non-null entry is the robot dict. The parser uses `next((r for r in robot_list if isinstance(r, dict)), None)` to locate it safely.

### `MODE_PAUSE` is an alias for `MODE_REMOTE` (==2)

Earlier code used the name `MODE_PAUSE`. Mode 2 is actually the Remote-control surface, not a cycle pause. The pause_cleaning() method sends mode==2, placing the robot into Remote-control state.

### `RUNTIME_EXTENSION_STEP_MIN = 15`

Runtime extension adjusts the wire `stepper` field in 15-minute increments. The `set_runtime_extension()` method validates that the supplied value is a non-negative multiple of 15.

### Equipment state wrapped in `"robot.1"` key

Cyclonext write frames wrap their equipment payload under the literal string key `"robot.1"` (with a dot). This differs from cyclobat, which nests under `equipment.robot.main`.

## WebSocket State Subscription (reduce polling)

To reduce polling and match the vendor app, `CyclonextSystem` supports a persistent WebSocket state subscription over the shared `AqualinkClient.ws_connect` transport.

**Protocol** (captured from the vendor app, `wss://prod-socket.zodiac-io.com/devices`):

1. On connect, send an Authorization `subscribe` frame: `{"action":"subscribe","version":1,"namespace":"authorization","service":"Authorization","payload":{"userId":<id>},"target":<serial>}` (built by `iaqualink.shared.robots.build_subscribe_frame`).
2. The cloud replies with an Authorization ack carrying the **full** reported state at `payload.robot.state.reported.equipment["robot.1"]` — applied via `_apply_reported_state`.
3. It then streams `StateStreamer` / `StateReported` frames. `payload.state.reported` frames are **deltas** (only changed fields under `equipment["robot.1"]`) — merged into the cached robot state and re-derived via `_apply_robot_delta`. `payload.state.desired` frames are command echoes and are ignored.

Note the equipment shape differs from the REST shadow: REST nests the robot as a list under `equipment.robot`; the WS stream uses the dot-keyed `equipment["robot.1"]` dict. `_extract_robot` handles both.

**Behaviour:**

- `_refresh()` skips the REST shadow poll only while the WS is **connected** and delivered state within `WS_STATE_FRESH_SECS`; otherwise it polls REST. A WS keepalive ping (`WS_KEEPALIVE_SECS`) surfaces a silently dropped socket so the loop raises and `_ws_connected` flips false — freshness is then immediate, avoiding stale state.
- Lifecycle: the consumer (e.g. the HA integration) calls `start_ws_subscription()` to begin reduced polling and `stop_ws_subscription()` on teardown. `_ws_enabled` (default `True`) is a master switch. The consumer should `refresh()` once (REST) before starting the subscription so `ebox_*`/`control_box_vr` diagnostic devices are seeded (WS deltas only carry the robot subtree).

**Status:** implemented from a captured session; pending live hardware verification of the delta merge across all field types. Known follow-ups (TODO): auto-reconnect with backoff (drop currently degrades to REST until the next `start_ws_subscription`), a push callback so HA can update on change instead of on poll, and cancelling the background task on `AqualinkClient.close()`.

## Deltas vs Protocol Reference

None at present.

## See Also

- [Protocol Reference: cyclonext](../../reference/systems/cyclonext.md) — wire-level spec
- [API Reference: cyclonext](../../api/systems/cyclonext.md) — class and method docs
