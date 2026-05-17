# iAqua Implementation Notes

Implementation details for the iAqua system (`device_type: "iaqua"`). For the wire-level protocol, see [Protocol Reference: iAqua](../../reference/systems/iaqua.md).

## Overview

| Property | Value |
|----------|-------|
| `device_type` | `iaqua` |
| API host | `p-api.iaqualink.net` |
| Authentication | Session token (`session_id`) + Bearer `IdToken` |
| Update calls | `get_home` + `get_devices` (+ `get_onetouch` if supported) |
| Python class | `IaquaSystem` in `src/iaqualink/systems/iaqua/system.py` |

## System Status Lifecycle

Status is determined **solely from the `get_home` response** (`home_screen[*].status`). The `get_devices` and `get_onetouch` responses do not affect system status.

### Status mapping

| `home_screen.status` | `SystemStatus` | Color |
|----------------------|----------------|-------|
| `"Online"` | `ONLINE` | Green |
| `"Offline"` | `OFFLINE` | Red |
| `"Service"` | `SERVICE` | Yellow |
| `"Unknown"` | `UNKNOWN` | Red |
| `""` (empty) | `UNKNOWN` | Red |
| key absent | `UNKNOWN` | Red |
| unrecognised string | `UNKNOWN` + warning | Red |

### Request-level status

| Condition | `SystemStatus` |
|-----------|----------------|
| Network / HTTP error (non-401, non-429) | `DISCONNECTED` |
| HTTP 429 (throttled) | `UNKNOWN` |

`refresh()` resets status to `IN_PROGRESS` before issuing requests, matching the pull-to-refresh behaviour in the Jandy app.

## System-Specific Properties

Available after a successful `refresh()`:

```python
system.system_type   # IaquaSystemType: SPA_AND_POOL, POOL_ONLY, or DUAL
system.temp_unit     # IaquaTemperatureUnit: FAHRENHEIT ("F") or CELSIUS ("C")
```

## Design Decisions

### Authorization header format

The reference app sends the `IdToken` bare (no `Bearer` prefix) in the `Authorization` header on session requests. The current Python implementation sends `Bearer {id_token}`. This diverges from the reference but works against the production API.

### `get_home` extra parameters

The reference app sends `country` and `attached_test=true` query parameters on `get_home` requests. The Python implementation omits both. No observed difference in API response.

### Session host

The reference app uses `p-api.iaqualink.net`. The Python implementation uses `r-api.iaqualink.net`. Both work against the production API.

## Deltas vs Protocol Reference

| # | Observed reference | Current Python (`IaquaSystem`) |
|---|---|---|
| 1 | Session host: `p-api.iaqualink.net` | Uses `r-api.iaqualink.net` |
| 2 | `Authorization` header: bare `{IdToken}` (no prefix) | Sends `Bearer {id_token}` |
| 3 | `get_home` sends `country` and `attached_test=true` params | Neither param is sent |
| 4 | `sessionID` in query params | ✓ Matches reference (`client_id` = `session_id`) |
| 5 | `api_key` header on session requests | ✓ Matches reference |
| 6 | Response parsing: `home_screen` array flattened | ✓ Matches reference |
| 7 | Offline detection from `status` field in both `get_home` and `get_devices` | ✓ Matches reference |
| 8 | `devices_screen` aux entries start at index 3 | ✓ Matches reference (`[3:]`) |

## See Also

- [Protocol Reference: iAqua](../../reference/systems/iaqua.md) — wire-level spec
- [API Reference: iAqua](../../api/systems/iaqua.md) — class and method docs
