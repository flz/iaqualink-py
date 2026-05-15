# eXO Systems

eXO systems are Zodiac systems using the `zodiac-io.com` API with an AWS IoT-style shadow state model.

## Overview

| Property | Value |
|----------|-------|
| `device_type` | `exo` |
| API host | `prod.zodiac-io.com` |
| Authentication | JWT `IdToken` (Bearer) |
| Update call | Single shadow state fetch (`GET /devices/v1/{serial}/shadow`) |
| State updates | Desired/reported state pattern (`POST` with `state.desired`) |

## System Status

Status is read from `state.reported.aws.status` in the shadow response and mapped directly to `SystemStatus`.

### Status values

| `aws.status` | `SystemStatus` | Color |
|--------------|----------------|-------|
| `"connected"` | `CONNECTED` | Green |
| `"online"` | `ONLINE` | Green |
| `"offline"` | `OFFLINE` | Red |
| `"disconnected"` | `DISCONNECTED` | Red |
| `"unknown"` | `UNKNOWN` | Red |
| `"service"` | `SERVICE` | Yellow |
| `"firmware_update"` | `FIRMWARE_UPDATE` | Yellow |
| `"in_progress"` | `IN_PROGRESS` | Dim |
| `""` (empty) | `IN_PROGRESS` | Dim |
| key absent | `UNKNOWN` | Red |
| unrecognised string | `UNKNOWN` | Red |

### Request-level status

| Condition | `SystemStatus` |
|-----------|----------------|
| Network / HTTP error (non-401, non-429) | `DISCONNECTED` |
| HTTP 429 (throttled) | `UNKNOWN` |

### Status lifecycle

`refresh()` resets status to `IN_PROGRESS` before issuing the shadow request, matching the pull-to-refresh behaviour in the original Zodiac app.

```python
# Status before first update
assert system.status == SystemStatus.IN_PROGRESS

await system.refresh()

# Status reflects aws.status from shadow response
assert system.status == SystemStatus.CONNECTED
```
