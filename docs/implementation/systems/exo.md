# eXO Implementation Notes

Implementation details for the eXO system (`device_type: "exo"`). For the wire-level protocol, see [Protocol Reference: eXO](../../reference/systems/exo.md).

## Overview

| Property | Value |
|----------|-------|
| `device_type` | `exo` |
| API host | `prod.zodiac-io.com` |
| Authentication | JWT `IdToken` (Bearer) |
| Update call | Single shadow state fetch (`GET /devices/v1/{serial}/shadow`) |
| State updates | Desired/reported state pattern (`POST` with `state.desired`) |
| Python class | `ExoSystem` in `src/iaqualink/systems/exo/system.py` |

## System Status Lifecycle

Status is read from `state.reported.aws.status` in the shadow response and mapped directly to `SystemStatus`.

### Status mapping

| `aws.status` | `SystemStatus` | Color |
|--------------|----------------|-------|
| `"connected"` | `CONNECTED` | Green |
| `"online"` | `ONLINE` | Green |
| `"offline"` | `OFFLINE` | Red |
| `"disconnected"` | `DISCONNECTED` | Red |
| `"unknown"` | `UNKNOWN` | Red |
| `"service"` | `SERVICE` | Yellow |
| `"firmware_update"` | `FIRMWARE_UPDATE` | Yellow |
| `""` (empty) | `UNKNOWN` | Red |
| key absent | `UNKNOWN` | Red |
| unrecognised string | `UNKNOWN` + warning | Red |

### Request-level status

| Condition | `SystemStatus` |
|-----------|----------------|
| Network / HTTP error (non-401, non-429) | `DISCONNECTED` |
| HTTP 429 (throttled) | `UNKNOWN` |

`refresh()` resets status to `IN_PROGRESS` before issuing the shadow request.

## Design Decisions

### MQTT vs HTTP REST

The reference Android app uses MQTT exclusively for shadow get and update operations. The Python implementation polls the HTTP REST shadow endpoint (`GET /devices/v1/{serial}/shadow`), which exposes the same data. Desired state writes use the same REST endpoint instead of MQTT publish.

This is a deliberate simplification — the REST path works in production and avoids the complexity of managing a persistent MQTT connection.

### Shadow URL version

Two shadow URL versions exist in the production configuration: `/devices/v1/` (`tcx_filteration` config key) and `/devices/v2/` (`device_details`). The Python implementation uses v1, consistent with the `tcx_filteration` key used by the reference app for the EXO device type.

### Temperature unit

The reference shadow payload does not include a temperature unit field. The Python implementation hardcodes `temp_unit = "C"` — not contradicted by the reference app, which also treats eXO temperatures as Celsius.

### Heater device

The reference app derives a heater device from `heating.state` but does not expose it as a distinct entity in shadow processing. The Python implementation creates a separate `"heater"` device entry with only the `state` field. This is a library extension not observed in the reference.

### Stripped shadow fields

The Python implementation strips `boost_time`, `vsp_speed`, `sn`, `vr`, and `version` from the parsed shadow. The reference app also filters these fields in shadow processing, so this is consistent.

## Deltas vs Protocol Reference

| # | Observed reference | Current Python (`ExoSystem`) |
|---|---|---|
| 1 | Uses MQTT exclusively for shadow get/update | Polls HTTP REST `GET /devices/v1/{serial}/shadow` |
| 2 | Desired state sent via MQTT publish | POSTs desired state to same REST shadow URL |
| 3 | Shadow URL version: not applicable (MQTT) | Uses `/devices/v1/` path (matches `tcx_filteration` config key) |
| 4 | `Authorization` format for REST shadow: not observed | Sends bare `{id_token}` — consistent with other shadow endpoints |
| 5 | `boost_time`, `vsp_speed`, `sn`, `vr`, `version` present in shadow | Python strips these fields — consistent with reference filtering |
| 6 | Temperature unit not present as a shadow field | Python hardcodes `temp_unit = "C"` — not contradicted by reference |
| 7 | `heater` device derived from `heating.state` | Python creates a separate `"heater"` device entry — not observed in reference as a distinct entity |

## See Also

- [Protocol Reference: eXO](../../reference/systems/exo.md) — wire-level spec
- [API Reference: eXO](../../api/systems/exo.md) — class and method docs
