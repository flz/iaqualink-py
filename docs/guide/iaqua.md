# iAqua Systems

iAqua systems use the `iaqualink.net` API and are the original Jandy iAqualink systems.

## Overview

| Property | Value |
|----------|-------|
| `device_type` | `iaqua` |
| API host | `p-api.iaqualink.net` |
| Authentication | Session token + Bearer token |
| Update calls | `get_home` + `get_devices` (+ `get_onetouch` if supported) |

## System Status

System status is determined **solely from the `get_home` response** (`home_screen[*].status`). The `get_devices` and `get_onetouch` responses do not affect system status.

### Status values

| `home_screen.status` | `SystemStatus` | Color |
|----------------------|----------------|-------|
| `"Online"` | `ONLINE` | Green |
| `"Offline"` | `OFFLINE` | Red |
| `"Service"` | `SERVICE` | Yellow |
| `"Unknown"` | `UNKNOWN` | Red |
| `""` (empty) | `IN_PROGRESS` | Dim |
| key absent | `UNKNOWN` | Red |

### Request-level status

| Condition | `SystemStatus` |
|-----------|----------------|
| Network / HTTP error (non-401, non-429) | `DISCONNECTED` |
| HTTP 429 (throttled) | `UNKNOWN` |

### Status lifecycle

`update()` resets status to `IN_PROGRESS` before issuing any requests, matching the pull-to-refresh behaviour in the original Jandy app.

```python
# Status before first update
assert system.status == SystemStatus.IN_PROGRESS

await system.update()

# Status reflects home_screen.status
assert system.status == SystemStatus.ONLINE
```

## System-Specific Properties

These properties are available after a successful `update()` call:

```python
system.system_type   # IaquaSystemType: SPA_AND_POOL, POOL_ONLY, or DUAL
system.temp_unit     # IaquaTemperatureUnit: FAHRENHEIT ("F") or CELSIUS ("C")
```
