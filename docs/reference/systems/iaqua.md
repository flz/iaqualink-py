# iaqua — iQ20 Pool Controller Protocol

**Python system name:** `"iaqua"`
**Wire device type:** `"iQ20"`
**Protocol family:** Legacy REST session (polling, no real-time push)
**Auth:** See [client.md](../client.md)

---

## Overview

iQ20 pool controllers communicate through a single session endpoint on the `p-api.iaqualink.net` host. All operations — reads and writes — are `GET` requests to the same URL, differentiated by a `command` query parameter. There is no push or subscription mechanism; the client must poll.

---

## Session Endpoint

```
GET https://p-api.iaqualink.net/v2/mobile/session.json
```

**Headers (all requests):**

| Header | Value |
|---|---|
| `Authorization` | `{IdToken}` — bare Cognito JWT, no `Bearer` prefix |
| `api_key` | Production API key |
| `Accept` | `application/json` |

**Query parameters (all requests):**

| Parameter | Value |
|---|---|
| `actionID` | `"command"` (literal) |
| `command` | Command string (see below) |
| `serial` | Device serial number |
| `sessionID` | `session_id` from login response |

---

## Command Reference

### Read commands

Called on every `update()` cycle.

#### `get_home`

Returns system-level status and thermostat state. In addition to the common query params, the reference implementation sends:

| Extra param | Value |
|---|---|
| `country` | User's country code (lowercase) |
| `attached_test` | `"true"` |

**Response structure:** JSON object containing a `home_screen` key whose value is an array of single-key dicts. Flatten all dicts in the array to obtain the following fields:

| Field | Type | Description |
|---|---|---|
| `status` | string | System status — see Status enum below |
| `system_type` | string | Pool configuration — see SystemType enum below |
| `temp_scale` | string | `"F"` or `"C"` |
| `pool_temp` | string | Current pool temperature |
| `spa_temp` | string | Current spa temperature |
| `air_temp` | string | Ambient air temperature |
| `pool_set_point` | string | Pool target temperature |
| `spa_set_point` | string | Spa target temperature |
| `pool_chill_set_point` | string | Pool chill (cooling) set point |
| `pool_pump` | string | Pool pump state (Toggle enum) |
| `spa_pump` | string | Spa pump state (Toggle enum) |
| `pool_heater` | string | Pool heater state (HeaterState enum) |
| `spa_heater` | string | Spa heater state (HeaterState enum) |
| `solar_heater` | string | Solar heater state (HeaterState enum) |
| `cover_pool` | string | Pool cover state (Toggle enum) |
| `freeze_protection` | string | Freeze protection state (Toggle enum) |
| `swc_set_point` | string | Salt water chlorinator set point |
| `swc_boost` | string | SWC boost mode active (Toggle enum) |
| `swc_low` | string | SWC low-salt warning (Toggle enum) |
| `is_icl_present` | string | ICL (Intellicenter Light) present flag |
| `acl_value` | string | ACL sensor value |
| `spa_salinity` | string | Spa salinity reading |
| `pool_salinity` | string | Pool salinity reading |
| `orp` | string | ORP sensor value |
| `ph` | string | pH sensor value |
| `heatpump_info` | object | Heat pump sub-status (nested) |
| `swc_info` | object | SWC sub-status (nested) |

If `status` is `"Offline"` or `"Service"`, no further fields should be trusted — raise an offline exception. If `system_type` is an empty string, skip processing the home screen update for this cycle.

#### `get_devices`

Returns the list of configurable aux outputs.

**Response structure:** JSON object containing a `devices_screen` key whose value is an array.

- Index 0: object with `status` field (same Status enum; repeat offline check).
- Index 1–2: reserved/informational; not used for device state.
- Index 3+: each element is a single-key dict whose key is the aux name (e.g., `"aux_1"`, `"aux_2"`). The value is an array of single-key dicts; flatten to get:

| Field | Type | Description |
|---|---|---|
| `state` | string | Current state (Toggle enum) |
| `label` | string | User-assigned label |
| `icon` | string | Icon identifier |
| `type` | string | Device type code — `"0"` generic, `"1"` dimmable light, `"2"` colour light |
| `subtype` | string | Light subtype when `type` is `"2"` |

If any state value is `"NaN"`, skip the devices-screen update for this cycle.

---

### Write commands

All write commands share the same endpoint and common headers/params. Each returns the same response shape as the corresponding read command; parse it the same way to update local state.

#### Pump and heater toggles

| Command | What it toggles |
|---|---|
| `set_pool_pump` | Pool pump on/off |
| `set_spa_pump` | Spa pump on/off |
| `set_pool_heater` | Pool heater on/off |
| `set_spa_heater` | Spa heater on/off |
| `set_solar_heater` | Solar heater on/off |

No extra parameters. Response: parse as `get_home`.

#### `set_aux_{n}`

Toggle aux output number `n`. Command string is `set_aux_{n}` where `n` is the numeric suffix of the aux key (e.g., aux key `aux_3` → command `set_aux_3`).

No extra parameters. Response: parse as `get_devices`.

#### `set_light`

Control a colour light output.

| Extra param | Value |
|---|---|
| `aux` | Aux slot identifier |
| `subtype` | Light subtype string |
| `light` | Target light mode/color |

Response: parse as `get_devices`.

#### `set_temps`

Set pool and/or spa target temperatures. Both temperatures must always be sent together.

| Extra param | Value |
|---|---|
| `temp1` | Spa target temperature (if spa present), then pool |
| `temp2` | Pool target temperature (if spa present) |

When only a pool is configured, send `temp1` = pool target only.

Response: parse as `get_home`.

---

## Enum Wire Values

All enum fields are serialized as strings in JSON.

### SystemType

| Wire value | Meaning |
|---|---|
| `"0"` | Spa and pool |
| `"1"` | Pool only |
| `"2"` | Dual (two pools) |
| `"-1"` | Unknown |

### Status

| Wire value | Meaning |
|---|---|
| `"Online"` | System reachable |
| `"Offline"` | System unreachable — raise offline exception |
| `"Service"` | System in service mode — treat as offline |
| `"Unknown"` | Unknown |

### HeaterState

| Wire value | Meaning |
|---|---|
| `"0"` | Off |
| `"1"` | On (active heating) |
| `"3"` | Enabled (setpoint maintained, not actively firing) |
| `"-1"` | Unknown |

### Toggle

| Wire value | Meaning |
|---|---|
| `"0"` | Off |
| `"1"` | On |
| `"-1"` | Unknown |

### TemperatureUnit

| Wire value | Meaning |
|---|---|
| `"F"` | Fahrenheit |
| `"C"` | Celsius |
| `"Unknown"` | Unknown |

---

## Error Handling

| Condition | Detection | Action |
|---|---|---|
| System offline or in service | `status` field = `"Offline"` or `"Service"` in any response | Raise offline exception |
| Device state NaN | Any `state` value = `"NaN"` in `devices_screen` | Skip devices update; no exception |
| HTTP 401 | Response code | Trigger token refresh, retry once |
| HTTP 429 | Response code | Re-raise throttle exception before broader service exception |
| Other HTTP error | Response code ≠ 200 | Raise service exception |

## See Also

- [Implementation Notes: iAqua](../../implementation/systems/iaqua.md) — status lifecycle, design decisions, accepted divergences from this spec
