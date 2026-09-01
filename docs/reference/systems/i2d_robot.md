# i2d_robot Protocol Reference

## Overview

`i2d_robot` is the `device_type` value returned in the device list for
Polaris iqPump robot cleaners. All cloud communication goes through
`https://r-api.iaqualink.net`. The protocol uses HTTP-only POST requests
with hex-encoded request/response strings — there is no WebSocket path.

Polaris is a Zodiac sub-brand; the same `r-api.iaqualink.net` host is
shared with the `i2d` iQPump pump system.

---

## Authentication

All requests require two headers:

| Header | Value |
|---|---|
| `Authorization` | `{IdToken}` — the Cognito JWT returned at login in `userPoolOAuth.IdToken` |
| `api_key` | `EOOEMOW4YR6QNB07` — the production API key |

`IdToken` is sent **bare** (no `Bearer` prefix), matching the existing
`i2d` pump pattern on this host.

---

## Endpoint

### POST /v2/devices/{serial}/control.json

Full URL: `https://r-api.iaqualink.net/v2/devices/{serial}/control.json`

Used for **all** i2d_robot operations — both status poll (read) and all write
commands (start, stop, return-to-base). The operation is selected by the
`params` field in the JSON body.

**Request headers:**

```
Authorization: {IdToken}
api_key: EOOEMOW4YR6QNB07
Content-Type: application/json
```

**Request body:**

```json
{
  "command":  "/command",
  "params":   "request={HEX}",
  "user_id":  {user_id}
}
```

- `command` is always the string `"/command"`.
- `params` is `"request={HEX}"` where `{HEX}` is one of the request hex
  strings from the table below.
- `user_id` is the integer user ID string returned at login.

**Response shape:**

```json
{
  "command": {
    "request":  "{HEX}",
    "response": "{36-char hex string}"
  }
}
```

The library verifies that `command.request` echoes back `I2D_REQUEST_STATUS`
(`OA11`); a mismatch is treated as an offline signal.

---

## Request Hex Strings

| Request | Hex | Notes |
|---|---|---|
| Status (read) | `OA11` | Note: leading character is letter 'O', not zero |
| Start cleaning | `0A1240&timeout=800` | |
| Stop cleaning | `0A1210&timeout=800` | |
| Return to base | `0A1701&timeout=800` | |

The status request hex `OA11` uses a **lowercase letter 'O'** as the first
character. This is the vendor magic and must be sent verbatim. See
[Implementation Notes](../../implementation/systems/i2d_robot.md) for
the rationale.

---

## Status Response Format

The `command.response` field is a 36-character hex string encoding 18 bytes
of robot state.

### 18-byte layout

| Offset | Bytes | Field | Notes |
|---|---|---|---|
| 0–1 | 2 | reserved | Header bytes, not interpreted |
| 2 | 1 | `state_code` | See §State Codes |
| 3 | 1 | `error_code` | See §Error Codes |
| 4 | 1 | mode byte | Low nibble = `mode_code`; high nibble ≠ 0 → `canister_full` |
| 5 | 1 | `time_remaining_min` | Minutes remaining in current clean cycle |
| 6–8 | 3 | `uptime_min` | Cumulative uptime minutes, little-endian |
| 9–11 | 3 | `total_hours` | Total operating hours, little-endian |
| 12–14 | 3 | `hardware_id` | Hardware identifier (exposed as hex string) |
| 15–17 | 3 | `firmware_id` | Firmware identifier (exposed as hex string) |

### State Codes (`state_code` byte)

| Hex | Label |
|---|---|
| `0x01` | `idle_or_docked` |
| `0x02` | `cleaning_just_started` |
| `0x03` | `finished` |
| `0x04` | `actively_cleaning` |
| `0x0C` | `paused` |
| `0x0D` | `error_state_d` |
| `0x0E` | `error_state_e` |

Unknown values render as `"unknown_{NN:02X}"`.

The `running` binary sensor is `True` when `state_code` is `0x02`
(`cleaning_just_started`) or `0x04` (`actively_cleaning`).

### Error Codes (`error_code` byte)

| Hex | Label |
|---|---|
| `0x00` | `no_error` |
| `0x01` | `pump_short_circuit` |
| `0x02` | `right_drive_motor_short_circuit` |
| `0x03` | `left_drive_motor_short_circuit` |
| `0x04` | `pump_motor_overconsumption` |
| `0x05` | `right_drive_motor_overconsumption` |
| `0x06` | `left_drive_motor_overconsumption` |
| `0x07` | `floats_on_surface` |
| `0x08` | `running_out_of_water` |
| `0x0A` | `communication_error` |

Unknown values render as `"unknown_{NN:02X}"`.

### Mode Codes (low nibble of mode byte)

| Hex | Label |
|---|---|
| `0x00` | `quick_clean_floor_only_standard` |
| `0x03` | `deep_clean_floor_and_walls_high_power` |
| `0x04` | `waterline_only_standard` |
| `0x08` | `quick_floor_only_standard` |
| `0x09` | `custom_floor_only_high_power` |
| `0x0A` | `custom_floor_and_walls_standard` |
| `0x0B` | `custom_floor_and_walls_high_power` |
| `0x0C` | `waterline_only_standard_v2` |
| `0x0D` | `custom_waterline_high_power` |
| `0x0E` | `custom_waterline_standard` |

Unknown values render as `"unknown_{NN:02X}"`.

---

## Device Map

After a successful refresh, `system.devices` contains:

| Key | Type | Value |
|---|---|---|
| `state_code` | `I2dSensor` | Raw integer state code |
| `state` | `I2dSensor` | Human-readable state label |
| `error_code` | `I2dSensor` | Raw integer error code |
| `error` | `I2dSensor` | Human-readable error label |
| `mode_code` | `I2dSensor` | Raw integer mode code |
| `mode` | `I2dSensor` | Human-readable mode label |
| `time_remaining_min` | `I2dSensor` | Minutes remaining in current cycle |
| `uptime_minutes` | `I2dSensor` | Cumulative uptime minutes |
| `total_hours` | `I2dSensor` | Total operating hours |
| `hardware_id` | `I2dSensor` | Hardware ID hex string |
| `firmware_id` | `I2dSensor` | Firmware ID hex string |
| `canister_full` | `I2dBinarySensor` | `True` when high nibble of mode byte is non-zero |
| `running` | `I2dBinarySensor` | `True` when actively cleaning or just started |
| `model_number` | `I2dSensor` | System `id` field from device list (if present) |

---

## See Also

- [Implementation Notes: i2d_robot](../../implementation/systems/i2d_robot.md)
- [API Reference: i2d_robot](../../api/systems/i2d_robot.md)
