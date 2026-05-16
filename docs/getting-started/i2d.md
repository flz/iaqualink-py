# i2d Systems (iQPump)

i2d systems are Jandy iQPump variable-speed pump controllers using the `r-api.iaqualink.net` control API.

## Overview

| Property | Value |
|----------|-------|
| `device_type` | `i2d` |
| API host | `r-api.iaqualink.net` |
| Authentication | Bearer `IdToken` + `api_key` header |
| Update call | Single `POST /v2/devices/{serial}/control.json` with `command=/alldata/read` |
| Write commands | Same endpoint with `command=/{key}/write`, `params=value={val}` |

## System Status

Status is determined from the `alldata.opmode` field in the response.

### Status values

| Condition | `SystemStatus` |
|-----------|----------------|
| `opmode` present and `<= 3` | `CONNECTED` |
| `opmode` present and `> 3` | `SERVICE` |
| `opmode` absent, `updateprogress` not `"0"` / `"0/0"` | `FIRMWARE_UPDATE` |
| `opmode` absent, `updateprogress` is `"0"` or `"0/0"` | `UNKNOWN` |
| Device offline (see below) | `OFFLINE` |
| Network / HTTP error (non-401, non-429) | `DISCONNECTED` |
| HTTP 429 (throttled) | `UNKNOWN` |

### Device offline

The server signals device-offline in two ways, both treated identically by the library:

1. **HTTP 200 with error body** — the API is reachable but the device is not:
   ```json
   {"status":"500","error":{"error_code":"error_internal_server_error","message":"Device offline.","details":"..."}}
   ```

2. **HTTP 500** — the API itself returns a 5xx with the same body structure.

In both cases, `system.status` is set to `SystemStatus.OFFLINE` and `refresh()` returns normally — no exception is raised to the caller.

### Implementation notes

**`updateprogress "0"` is treated as no-update-in-progress.** When `opmode` is absent and `updateprogress="0"`, the library sets `UNKNOWN` (same as `"0/0"`). The reference app treats `"0"` as distinct from `"0/0"` and considers the device reachable in that state. In practice this path is unreachable during normal operation (`opmode` is always present then); `UNKNOWN` is the conservative choice for the ambiguous case.

## Device Breakdown

| Device class | Key(s) | Type |
|---|---|---|
| `I2dPump` | `{serial}` | Pump on/off, presets, speed percentage |
| `I2dNumber` | `globalrpmmin`, `globalrpmmax`, `customspeedrpm`, … | Writable numeric setting |
| `I2dSwitch` | `freezeprotectenable` | Binary on/off setting |
| `I2dSensor` | `speed`, `power`, `temperature`, `horsepower`, timers, `currentspan`, WiFi fields | Read-only telemetry |
| `I2dBinarySensor` | `freezeprotectstatus` | Read-only binary flag |

See the [API reference](../reference/i2d.md) for full field documentation.
