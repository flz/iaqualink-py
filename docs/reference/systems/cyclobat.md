# cyclobat — Zodiac Robot Cleaner Protocol

**Python system name:** `"cyclobat"`
**Protocol family:** AWS IoT shadow (REST polling for reads; WebSocket for writes)
**Auth:** See [client.md](../client.md)

---

## Overview

Cyclobat battery-powered robot cleaners expose their state via an AWS IoT device shadow REST endpoint. The Python implementation polls this endpoint for reads and uses a persistent WebSocket connection for write commands (start, stop, return-to-base).

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

Write commands are sent as JSON frames via the shared `_robot_ws` (`CyclobatWs`). The action is `setCleaningMode` with a payload targeting `equipment.robot.main.ctrl`.

### Frame shape

```json
{
  "action": "setCleaningMode",
  "version": 1,
  "clientToken": "{user_id}|{auth_token}|{app_client_id}",
  "serial": "{serial}",
  "payload": {
    "equipment": {
      "robot": {
        "main": {
          "ctrl": 1
        }
      }
    }
  }
}
```

**`clientToken` format:** `{user_id}|{authentication_token}|{app_client_id}` where `app_client_id` is `cognitoPool.appClientId` from the login response.

---

## Reported State Schema

The Python implementation reads `state.reported.equipment.robot`.

### Top-level robot fields

| Field | Type | Description |
|---|---|---|
| `vr` | string | Firmware version |
| `sn` | string | Serial number |
| `modelNumber` | string | Model number string |

### `main` — cleaning state

| Field | Type | Description |
|---|---|---|
| `state` | integer | Current state: `0`=stopped, `1`=cleaning, `3`=returning |
| `ctrl` | integer | Write target — same encoding as `state` |
| `mode` | integer | Cleaning mode |
| `error` | integer | Error code (`0` = none) |
| `cycleStartTime` | integer | Unix timestamp (seconds) when current cycle started |

### `battery` — battery status

| Field | Type | Description |
|---|---|---|
| `vr` | string | Battery firmware version |
| `state` | integer | Battery state code |
| `userChargePerc` | integer | Charge percentage (0–100) |
| `userChargeState` | integer | Charge state code |
| `cycles` | integer | Total charge cycles |
| `warning.code` | integer | Warning code (`0` = none) |

### `stats` — lifetime statistics

| Field | Type | Description |
|---|---|---|
| `totRunTime` | integer | Total run time (minutes) |
| `diagnostic` | integer | Diagnostic code |
| `tmp` | integer | Temperature |
| `lastError.code` | integer | Last error code |
| `lastError.cycleNb` | integer | Cycle number of last error |

### `lastCycle` — most recent completed cycle

| Field | Type | Description |
|---|---|---|
| `cycleNb` | integer | Cycle count |
| `duration` | integer | Cycle duration (minutes) |
| `mode` | integer | Mode used |
| `endCycleType` | integer | Cycle type index (0–3); used as key into `cycles` duration table |
| `errorCode` | integer | Error code at end of cycle |

### `cycles` — cycle duration table

Each sub-object contains a `duration` field in **minutes**.

| Key | Description |
|---|---|
| `floorTim` | Floor-only cycle |
| `floorWallsTim` | Floor + walls cycle |
| `smartTim` | Smart cycle |
| `waterlineTim` | Waterline cycle |

Additional fields:

| Field | Type | Description |
|---|---|---|
| `firstSmartDone` | boolean | Whether the first smart cycle has completed |
| `liftPatternTim` | integer | Lift pattern timing value |

---

## Write Commands

All writes use action `setCleaningMode`. Only `main.ctrl` needs to be set.

| `ctrl` | Meaning |
|---|---|
| `0` | Stop |
| `1` | Start cleaning |
| `3` | Return to base / dock |

---

## Error Handling

| Condition | Detection | Action |
|---|---|---|
| HTTP 401 | Response code | Trigger token refresh, retry once |
| HTTP 429 | Response code | Re-raise throttle exception before broader service exception |
| Other HTTP error | Response code ≠ 200 | Raise service exception |
| `equipment.robot` absent | Key missing in shadow | Raise `_AqualinkOfflineSignal` → base sets `OFFLINE` |

## See Also

- [Implementation Notes: cyclobat](../../implementation/systems/cyclobat.md) — status lifecycle, design decisions, accepted divergences from this spec
