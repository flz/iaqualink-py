# cyclonext — Zodiac Wired Robot Cleaner Protocol

**Python system name:** `"cyclonext"`
**Protocol family:** AWS IoT shadow (REST polling for reads; WebSocket for writes)
**Auth:** See [client.md](../client.md)

---

## Overview

Cyclonext wired robot cleaners expose their state via an AWS IoT device shadow REST endpoint. The Python implementation polls this endpoint for reads and uses a WebSocket connection for write commands (start, stop, remote control, lift system).

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

Write commands are sent as JSON frames. The action is `setCleanerState` with namespace `cyclonext`. Equipment payload is wrapped in the literal string key `"robot.1"` (with a dot — cyclonext-specific).

### Frame shape

```json
{
  "action": "setCleanerState",
  "namespace": "cyclonext",
  "version": 1,
  "clientToken": "{user_id}|{auth_token}|{app_client_id}",
  "serial": "{serial}",
  "payload": {
    "equipment": {
      "robot.1": {
        "mode": 1
      }
    }
  }
}
```

**`clientToken` format:** `{user_id}|{authentication_token}|{app_client_id}` when `app_client_id` is set (3-part), otherwise `{user_id}|<random-uuid>` (2-part fallback). Cyclonext accepts the 2-part fallback; cyclobat requires 3-part.

---

## Reported State Schema

The Python implementation reads `state.reported.equipment.robot`.

`state.reported.equipment.robot` is a **list**. Index 0 is always null; the first non-null (dict) entry is the robot object.

### Robot fields

| Field | Type | Notes |
|---|---|---|
| `mode` | int | 0=stopped, 1=running, 2=remote_control, 3=lift_system |
| `cycle` | int | 1=floor, 3=floor_and_walls (observed on Alpha series) |
| `cycleStartTime` | int | Unix seconds when cycle began |
| `stepper` | int | Runtime extension in minutes |
| `durations` | dict | Keys: `customTim`, `deepTim`, `firstSmartTim`, `quickTim`, `scanTim`, `smartTim`, `waterTim`. Values in **minutes**. |
| `errors.code` | int | Active error code; 0 = OK |

### `eboxData` — control-box hardware identifiers

`state.reported.eboxData` contains control-box hardware fields. Each key surfaces as `ebox_<key>` in the device registry.

### `vr` — control-box firmware version

`state.reported.vr` surfaces as `control_box_vr`.

---

## Cycle → Duration Key Mapping

| `cycle` | `durations` key |
|---|---|
| 1 (floor) | `quickTim` |
| 3 (floor_and_walls) | `deepTim` |

---

## Write Payload Shape

All cyclonext writes wrap their equipment state in `{"robot.1": {...}}`.

| Frame purpose | `equipment_state` |
|---|---|
| Set mode | `{"robot.1": {"mode": N}}` |
| Set cycle | `{"robot.1": {"cycle": N}}` |
| Set stepper | `{"robot.1": {"stepper": minutes}}` |
| Remote/Lift state | `{"robot.1": {"mode": N, "direction": D}}` |

---

## Mode Enum

| `mode` | Meaning |
|---|---|
| 0 | Stopped |
| 1 | Running |
| 2 | Remote control (also reused as Pause) |
| 3 | Lift system |

---

## Direction Enum — Remote Control (mode=2)

| `direction` | Meaning |
|---|---|
| 0 | Stop |
| 1 | Forward |
| 2 | Backward |
| 3 | Rotate right |
| 4 | Rotate left |

---

## Direction Enum — Lift System (mode=3)

| `direction` | Meaning |
|---|---|
| 0 | Stop |
| 5 | Eject |
| 6 | Rotate left |
| 7 | Rotate right |

---

## Error Handling

| Condition | Detection | Action |
|---|---|---|
| HTTP 401 | Response code | Trigger token refresh, retry once |
| HTTP 429 | Response code | Re-raise throttle exception before broader service exception |
| Other HTTP error | Response code ≠ 200 | Raise service exception |
| `equipment.robot` list has no dict entry | Parse check | Raise `_AqualinkOfflineSignal` → base sets `OFFLINE` |

## See Also

- [Implementation Notes: cyclonext](../../implementation/systems/cyclonext.md) — status lifecycle, design decisions, accepted divergences from this spec
