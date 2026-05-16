# exo — EXO/SWC Chlorinator Protocol

**Python system name:** `"exo"`
**Protocol family:** AWS IoT shadow (MQTT in reference; REST polling in current Python implementation)
**Auth:** See [client.md](client.md)

---

## Overview

EXO salt water chlorinator devices expose their state via an AWS IoT device shadow. The reference Android implementation uses MQTT exclusively to fetch and update shadow state. The current Python implementation uses HTTP REST to poll the same shadow data, which is also exposed as a REST endpoint.

---

## Shadow Endpoints (REST)

Two URL versions exist in the production configuration:

| Config key | Path | Notes |
|---|---|---|
| `tcx_filteration` | `/devices/v1/{serial}/shadow` | v1 — used by current Python implementation |
| `device_details` | `/devices/v2/{serial}/shadow` | v2 — purpose unclear; may be for other device types |

### Fetch shadow state

```
GET https://prod.zodiac-io.com/devices/v1/{serial}/shadow
Authorization: {IdToken}
```

No request body.

### Post desired state

```
POST https://prod.zodiac-io.com/devices/v1/{serial}/shadow
Authorization: {IdToken}
Content-Type: application/json

{
  "state": {
    "desired": { ... }
  }
}
```

---

## Shadow State Structure

The full shadow response envelope:

```json
{
  "state": {
    "reported": { ... },
    "desired":  { ... }
  }
}
```

The Python implementation reads only `state.reported`.

### `state.reported` field reference

#### `equipment.swc_0` — chlorinator core

| Field | Type | Description |
|---|---|---|
| `swc` | integer | Chlorine production percentage (0–100) |
| `swc_low` | integer | Low-salt warning flag (0/1) |
| `production` | integer | Current production level |
| `boost` | integer | Boost mode active (0/1) |
| `boost_time` | string | Boost remaining time — stripped by current Python implementation |
| `exo_state` | integer | Device operating state |
| `error_code` | integer | Error code (0 = none) |
| `error_state` | integer | Error state flag |
| `temp` | string | Water temperature reading |
| `amp` | string | Current draw |
| `low` | integer | Low-production indicator |
| `lang` | integer | Language setting |
| `vsp` | string | Variable speed pump identifier — stripped |
| `vr` | string | Firmware version — stripped |
| `sn` | string | Serial number — stripped |
| `ph_sp` | integer | pH set point |
| `ph_only` | string | pH-only mode flag |
| `orp_sp` | integer | ORP set point |
| `aux230` | string | 230 V aux output state |
| `dual_link` | string | Dual-link mode flag |
| `filter_pump` | object | Filter pump state (see below) |
| `vsp_speed` | object | Variable speed pump RPM bounds — stripped |
| `sns_1` | object | Sensor 1 readings (see below) |
| `sns_2` | object | Sensor 2 readings |
| `sns_3` | object | Sensor 3 readings |
| `aux_1` | object | Aux output 1 state (see below) |
| `aux_2` | object | Aux output 2 state |

**`filter_pump` object:**

| Field | Type | Description |
|---|---|---|
| `state` | integer | 0 = off, 1 = on |
| `type` | integer | Pump type code |

**`sns_N` sensor object:**

| Field | Type | Description |
|---|---|---|
| `sensor_type` | integer | Sensor type code |
| `state` | integer | Sensor state |
| `value` | number | Sensor reading |

**`aux_N` aux output object:**

| Field | Type | Description |
|---|---|---|
| `type` | integer | Output type |
| `mode` | integer | Operating mode |
| `color` | integer | Color setting (for lights) |
| `state` | integer | 0 = off, 1 = on |

#### `heating` — heating control

Present only if the device has a heating module.

| Field | Type | Description |
|---|---|---|
| `state` | integer | Heater active (0/1) |
| `enabled` | integer | Heating function enabled (0/1) |
| `priority_enabled` | integer | Priority heating enabled (0/1) |
| `sp` | integer | Temperature set point |
| `sp_min` | integer | Minimum allowed set point |
| `sp_max` | integer | Maximum allowed set point |
| `vsp_rpm_index` | integer | Currently selected VSP speed index |
| `vsp_rpm_list` | object | Map of speed-name → RPM integer (dynamic keys) |

#### `schedules` — schedule entries

Object whose keys are schedule identifiers (dynamic). Each schedule entry:

| Field | Type | Description |
|---|---|---|
| `timer.start` | string | Start time (HH:MM format) |
| `timer.end` | string | End time (HH:MM format) |
| `rpm` | integer | Target RPM for this schedule |
| `name` | string | User-assigned schedule name |

#### Top-level reported fields

| Field | Type | Description |
|---|---|---|
| `hs.t1` | number | Water temperature (primary sensor) |
| `tr` | number | Return temperature |
| `vr` | string | Device firmware version |
| `ty` | string | Device type string |
| `aws.status` | string | AWS connectivity status |
| `aws.session_id` | string | AWS session identifier |
| `aws.timestamp` | string | Last AWS contact timestamp |

---

## Write Operations

All writes use the desired-state POST (see Endpoints above). Only include the fields being changed — omit unchanged fields.

### Set aux output state

```json
{
  "state": {
    "desired": {
      "equipment": {
        "swc_0": {
          "{aux_name}": {
            "state": 0
          }
        }
      }
    }
  }
}
```

### Set toggle (scalar output)

For fields under `swc_0` that are scalars (not nested objects):

```json
{
  "state": {
    "desired": {
      "equipment": {
        "swc_0": {
          "{field_name}": {value}
        }
      }
    }
  }
}
```

### Set heating state

```json
{
  "state": {
    "desired": {
      "heating": {
        "{field_name}": {value}
      }
    }
  }
}
```

### Set filter pump state

```json
{
  "state": {
    "desired": {
      "equipment": {
        "swc_0": {
          "{pump_name}": {
            "state": 0
          }
        }
      }
    }
  }
}
```

---

## MQTT Transport (Reference)

The reference implementation does not poll via HTTP. It subscribes to AWS IoT MQTT topics using short-lived Cognito session credentials (accessKeyId, secretKey, sessionToken). This section documents the observed reference behavior for completeness.

**MQTT broker:** `a1zi08qpbrtjyq-ats.iot.us-east-1.amazonaws.com`
**Transport:** TLS
**Client ID:** UUID, generated fresh per session
**Keepalive:** 60 seconds
**Auto-resubscribe:** Yes
**Max reconnect attempts:** 5

**Topic patterns:**

| Operation | Topic |
|---|---|
| Request full shadow | `$aws/things/{serial}/shadow/get` (publish empty payload) |
| Receive full shadow | `$aws/things/{serial}/shadow/get/accepted` (subscribe) |
| Subscribe to delta updates | `$aws/things/{serial}/shadow/update/accepted` (subscribe) |
| Post desired state | `$aws/things/{serial}/shadow/update` (publish) |
| OTA events | `events/iaqualink/{serial}/{type}` (subscribe) |

The EXO device is identified at the MQTT routing layer by a device-type ordinal. Shadow messages for EXO are dispatched based on the `device_type` field in the device list response.

---

## Error Handling

| Condition | Detection | Action |
|---|---|---|
| HTTP 401 | Response code | Trigger token refresh, retry once |
| HTTP 429 | Response code | Re-raise throttle exception before broader service exception |
| Other HTTP error | Response code ≠ 200 | Raise service exception |
| System offline | Not observed as a field in shadow state — not observed in reference | Not observed in reference |

---

## Deltas vs Current Implementation

| # | Observed reference | Current Python (`ExoSystem`) |
|---|---|---|
| 1 | Uses MQTT exclusively for shadow get/update | Polls HTTP REST `GET /devices/v1/{serial}/shadow` |
| 2 | Desired state sent via MQTT publish | POSTs desired state to same REST shadow URL |
| 3 | Shadow URL version: not applicable (MQTT) | Uses `/devices/v1/` path (matches `tcx_filteration` config key, not `device_details` which is v2) |
| 4 | `Authorization` format for REST shadow: not observed (MQTT path) | Sends bare `{id_token}` — consistent with other shadow endpoints |
| 5 | `boost_time`, `vsp_speed`, `sn`, `vr`, `version` present in shadow | Python strips these fields — consistent with reference (reference also filters them in shadow processing) |
| 6 | Temperature unit not present as a shadow field | Python hardcodes `temp_unit = "C"` — not contradicted by reference |
| 7 | `heater` device derived from `heating.state` | Python creates a separate `"heater"` device entry with only `state` — not observed in reference as a distinct entity |
