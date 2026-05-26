# vr — Zodiac Variable-Speed Robot Cleaner Protocol

**Python system name:** `"vr"`
**Protocol family:** AWS IoT shadow (REST polling for reads; WebSocket for writes)
**Auth:** See [client.md](../client.md)

---

## Overview

VR variable-speed robot cleaners expose their state via an AWS IoT device shadow REST endpoint. The Python implementation polls this endpoint for reads and uses a WebSocket connection for write commands (start, stop, pause, return-to-base, cycle selection, runtime extension, and remote steering).

---

## Shadow Endpoint (REST Read)

```
GET https://prod.zodiac-io.com/devices/v1/{serial}/shadow
Authorization: {IdToken}
```

No request body. Response is an AWS IoT-shaped shadow envelope:

```json
{
  "state": {
    "reported": { ... }
  }
}
```

The Python implementation reads only `state.reported`.

---

## WebSocket Write Endpoint

```
wss://prod-socket.zodiac-io.com/devices
Authorization: {IdToken}
```

Write commands are sent as JSON frames. Equipment payload is wrapped in the literal string key `"robot"` (no dot — differs from cyclonext's `"robot.1"`).

### Frame shape

```json
{
  "version": 1,
  "action": "setCleanerState",
  "namespace": "vr",
  "target": "{serial}",
  "payload": {
    "clientToken": "{user_id}|{auth_token}|{app_client_id}",
    "state": {
      "desired": {
        "equipment": {
          "robot": {
            "state": 1
          }
        }
      }
    }
  }
}
```

**`clientToken` format:** `{user_id}|{authentication_token}|{app_client_id}` (3-part). `app_client_id` is sourced from `cognitoPool.appClientId` in the login response.

---

## Reported State Schema

The Python implementation reads `state.reported.equipment.robot`.

`state.reported.equipment.robot` is a **dict** (not a list — unlike cyclonext).

### Robot fields

| Field | Type | Notes |
|---|---|---|
| `state` | int | 0=stopped, 1=cleaning, 2=paused, 3=returning |
| `prCyc` | int | 0=wall_only, 1=floor_only, 2=smart_floor_and_walls, 3=floor_and_walls |
| `stepper` | int | Runtime extension in minutes |
| `cycleStartTime` | int | Unix seconds when cycle began |
| `durations` | dict | Per-cycle durations in minutes. Lookup by **ordinal index** of `prCyc` into values list. |
| `sensors.sns_1.val` | int/float | Water temperature (optional) |
| `sn` | str | Robot serial number |
| `vr` | str | Robot firmware version |

---

## State Enum

| `state` | Meaning |
|---|---|
| 0 | Stopped |
| 1 | Cleaning |
| 2 | Paused |
| 3 | Returning |

---

## Cycle Enum (`prCyc`)

| `prCyc` | Label |
|---|---|
| 0 | wall_only |
| 1 | floor_only |
| 2 | smart_floor_and_walls |
| 3 | floor_and_walls |

---

## Remote Control Enum (`rmt_ctrl`, action=`setRemoteSteeringControl`)

| `rmt_ctrl` | Meaning |
|---|---|
| 0 | Stop |
| 1 | Forward |
| 2 | Backward |
| 3 | Rotate right |
| 4 | Rotate left |

---

## Write Payload Shape

All VR writes wrap their equipment payload under the literal string key `"robot"` (note: `"robot"`, not `"robot.1"` as used by cyclonext).

| Frame purpose | `equipment_state` | action |
|---|---|---|
| Set state | `{"robot": {"state": N}}` | setCleanerState |
| Set cycle | `{"robot": {"prCyc": N}}` | setCleanerState |
| Set stepper | `{"robot": {"stepper": minutes}}` | setCleanerState |
| Remote steering | `{"robot": {"rmt_ctrl": N}}` | setRemoteSteeringControl |

---

## Remote Control Protocol

The caller must put the robot into `state == 2` (paused) before sending any `setRemoteSteeringControl` frame. The Python wrapper handles this automatically via `_enter_remote_mode`, which issues a `pause_cleaning()` call if the robot is not already paused.

---

## Error Handling

| Condition | Detection | Action |
|---|---|---|
| HTTP 401 | Response code | Trigger token refresh, retry once |
| HTTP 429 | Response code | Re-raise throttle exception before broader service exception |
| Other HTTP error | Response code ≠ 200 | Raise service exception |
| `equipment.robot` absent or not a dict | Parse check | Raise `_AqualinkOfflineSignal` → base sets `OFFLINE` |

---

## See Also

- [Implementation Notes: vr](../../implementation/systems/vr.md) — status lifecycle, design decisions, accepted divergences from this spec
