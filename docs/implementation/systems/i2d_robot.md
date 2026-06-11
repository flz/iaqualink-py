# i2d_robot Implementation Notes

Implementation details for i2d_robot systems (`device_type: "i2d_robot"` — Polaris
iqPump robot cleaners). For the wire-level protocol, see
[Protocol Reference: i2d_robot](../../reference/systems/i2d_robot.md).

## Overview

| Property | Value |
|----------|-------|
| `device_type` | `i2d_robot` |
| Manufacturer | Polaris (Zodiac sub-brand) |
| API host | `r-api.iaqualink.net` |
| Authentication | bare `IdToken` + `api_key` header |
| Transport | HTTP-only (no WebSocket) |
| Status call | `POST /v2/devices/{serial}/control.json` with `params=request=OA11` |
| Write commands | Same endpoint with different `params=request={HEX}` |
| Python class | `I2dRobotSystem` in `src/iaqualink/systems/i2d_robot/system.py` |

## System Status Lifecycle

Status is derived from the parsed hex response, not from an HTTP error code.

| Condition | `SystemStatus` |
|-----------|----------------|
| `command.response` parses successfully | `ONLINE` |
| `command.request` != `OA11` in response | `OFFLINE` (via `_AqualinkOfflineSignal`) |
| `command.response` fails hex parse | `OFFLINE` (via `_AqualinkOfflineSignal`) |
| HTTP 429 (throttled) | `UNKNOWN` |
| HTTP 5xx / transport error | `DISCONNECTED` |
| HTTP 401 (unauthorized) | `_AqualinkOfflineSignal` not raised; `AqualinkServiceUnauthorizedException` propagates |

`_refresh()` sets `self.status = SystemStatus.ONLINE` only after
`_parse_status_response()` returns normally. Any offline signal from the
parser raises `_AqualinkOfflineSignal` before that line, which `refresh()`
catches and converts to `OFFLINE`.

## HTTP-Only Design

Unlike the WebSocket-based robot systems (`cyclobat`, `cyclonext`, `vr`,
`vortrax`), `i2d_robot` uses HTTP POST for both reads and writes. There is no
`ws.py` dependency and no persistent connection. Each `refresh()` call
opens a fresh request.

This matches the `i2d` iQPump pump pattern on the same API host.

## Hex-Encoded Request/Response Protocol

Both the poll request and control commands encode their operation as a
hex string in the `params` field:

```
params = "request={HEX}"
```

The status request uses the magic string `OA11` (letter 'O', not zero). The
control commands (`0A1240&timeout=800`, etc.) use numeric `0` as the first
character. The `&timeout=800` suffix is passed verbatim as part of the `params`
string — the API parses it server-side.

## Status Response Parsing

`parse_status_hex()` in `protocol.py` converts the 36-character hex string to
an `I2dStatus` dataclass. Fields:

- `state_code` / `state_label` — byte 2 of the decoded bytes
- `error_code` / `error_label` — byte 3
- `mode_code` / `mode_label` — low nibble of byte 4
- `canister_full` — high nibble of byte 4 is non-zero
- `time_remaining_min` — byte 5
- `uptime_min` — bytes 6–8, little-endian 24-bit integer
- `total_hours` — bytes 9–11, little-endian 24-bit integer
- `hardware_id` — bytes 12–14 as hex string
- `firmware_id` — bytes 15–17 as hex string

Unknown state/error/mode values fall back to `f"unknown_{N:02X}"`.

## Device Model

All 13 sensors + 2 binary sensors share a simple `{"name": ..., "state": ...}`
data dict. Updating an existing device calls `data.update(v)` in-place so that
cached device references remain valid across `refresh()` calls.

### `running` binary sensor

`running` is derived, not a raw field from the protocol:

```python
_ACTIVE_STATE_CODES = frozenset({0x02, 0x04})  # cleaning_just_started, actively_cleaning
running = state_code in _ACTIVE_STATE_CODES
```

### `model_number` sensor

Populated from `self.data.get("id")` — the `id` field returned in the device
list response. Absent when `id` is not present in the system data.

## Write Commands

Three write methods send the corresponding hex request and discard the response
body (write responses are not parsed for state updates):

| Method | Hex |
|---|---|
| `start_cleaning()` | `0A1240&timeout=800` |
| `stop_cleaning()` | `0A1210&timeout=800` |
| `return_to_base()` | `0A1701&timeout=800` |

## Design Decisions

### `OA11` status request uses letter 'O'

The status request string `OA11` begins with the letter `'O'` (0x4F), not the
digit `'0'` (0x30). This is a vendor quirk documented in the protocol
reference. The constant `I2D_REQUEST_STATUS = "OA11"` is intentional and
must not be "corrected" to `"0A11"`.

### No local access path

The `i2d_robot` protocol does not define a local LAN access path (unlike `i2d`
pumps which expose an HTTP server at `192.168.0.1`). Cloud-only.

### Offline detection via response echo

The server always returns HTTP 200. Offline/error states are detected by
inspecting the `command.request` echo in the response body — a mismatch
signals `_AqualinkOfflineSignal`.

## See Also

- [Protocol Reference: i2d_robot](../../reference/systems/i2d_robot.md)
- [API Reference: i2d_robot](../../api/systems/i2d_robot.md)
