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

**Top-level response fields** (outside `home_screen`):

| Field | Type | Description |
|---|---|---|
| `message` | string | Informational message (may be empty) |
| `onetouch` | string | One Touch feature enabled — `"true"` or `"false"` |
| `web` | string | Web access enabled — `"true"` or `"false"` |
| `attached_device` | string | Identifier of attached device (may be empty) |
| `attached_system_fw_version` | string | Firmware version of attached system (may be empty) |

**Response structure:** JSON object containing a `home_screen` key whose value is an array of single-key dicts. Flatten all dicts in the array to obtain the following fields:

| Field | Type | Description |
|---|---|---|
| `status` | string | System status — see Status enum below |
| `response` | string | Raw response string (informational; not used for state) |
| `system_type` | string | Pool configuration — see SystemType enum below |
| `temp_scale` | string | `"F"` or `"C"` |
| `pool_temp` | string | Current pool temperature |
| `spa_temp` | string | Current spa temperature |
| `air_temp` | string | Ambient air temperature |
| `pool_set_point` | string | Pool target temperature |
| `spa_set_point` | string | Spa target temperature |
| `pool_chill_set_point` | string | Pool chill (cooling) set point; empty if no heat pump or chill unavailable |
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
| `is_icl_present` | string | ICL (Intellicenter Light) present flag; `"present"` when ICL hardware is paired |
| `icl_custom_color_info` | array | ICL custom colour zone data (see ICL section) |
| `acl_value` | string | ACL sensor value |
| `spa_salinity` | string | Spa salinity reading |
| `pool_salinity` | string | Pool salinity reading |
| `orp` | string | ORP sensor value |
| `ph` | string | pH sensor value |
| `relay_count` | string | Number of relay outputs available (numeric string, e.g. `"4"`) |
| `lockedout_message` | string | Message when system is locked out (may be empty) |
| `heatpump_info` | object | Heat pump sub-status (nested) — see below |
| `swc_info` | object | SWC sub-status (nested) — see SWC section |

If `status` is `"Offline"` or `"Service"`, no further fields should be trusted — raise an offline exception. If `system_type` is an empty string, skip processing the home screen update for this cycle.

#### `heatpump_info` object

Nested object under the flattened `home_screen` key `heatpump_info`. Present only when a heat pump is paired with the iQ20 controller.

| Field | Type | Description |
|---|---|---|
| `isheatpumpPresent` | boolean | Heat pump hardware is present and paired |
| `heatpumpstatus` | string | Current heat pump operational status (e.g. `"off"`, `"heat"`) |
| `isChillAvailable` | boolean | Whether chill (cooling) mode is available on this heat pump |
| `heatpumpmode` | string | Current mode — e.g. `"heat"` |
| `heatpumptype` | string | Hardware type string — e.g. `"4-wired"` |

#### `get_devices`

Returns the list of configurable aux outputs.

**Response structure:** JSON object containing a `devices_screen` key whose value is an array.

- Index 0: `{"status": "..."}` — Status enum; repeat offline check.
- Index 1: `{"response": "..."}` — Raw packed response string (informational; not used for device state).
- Index 2: `{"group": "..."}` — Group identifier string (informational).
- Index 3+: each element is a single-key dict whose key is the aux name (e.g., `"aux_1"`, `"aux_B1"`, `"aux_EA"`). Aux keys use the numeric suffix for the primary board (`aux_1`–`aux_7`), board-letter prefixes for expansion boards (`aux_B1`–`aux_B8`, `aux_C1`–`aux_C8`, `aux_D1`–`aux_D8`), and special suffixes like `aux_EA` for extra auxes. The value is an array of single-key dicts; flatten to get:

| Field | Type | Description |
|---|---|---|
| `state` | string | Current state (Toggle enum) |
| `label` | string | User-assigned label |
| `icon` | string | Icon identifier |
| `type` | string | Device type code — `"0"` generic, `"1"` dimmable light, `"2"` colour light, `"3"` SJVA |
| `subtype` | string | Light subtype when `type` is `"2"`; also used as a VSP assignment flag |

The response also contains a top-level `icl_info_list` array (outside `devices_screen`) when an ICL is present — see ICL section.

If any state value is `"NaN"`, skip the devices-screen update for this cycle.

#### `get_onetouch`

Returns the One Touch preset list.

**Response structure:** JSON object containing an `onetouch_screen` key whose value is an array of single-key dicts. Flatten all dicts in the array to obtain entries keyed by One Touch slot name (e.g. `"one_touch_1"`, `"one_touch_2"`, etc.) skipping the `"status"` and `"response"` keys. Each slot value is an array of single-key dicts; flatten to get:

| Field | Type | Description |
|---|---|---|
| `status` | string | Slot enabled state (Toggle enum — `"0"` off, `"1"` on) |
| `state` | string | Slot active state (Toggle enum — `"0"` inactive, `"1"` active) |
| `label` | string | User-assigned label for this preset |

Top-level `message` field is also present (may be empty).

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

Toggle aux output number `n`. Command string is `set_aux_{n}` where `n` is the full suffix of the aux key (e.g., aux key `aux_3` → command `set_aux_3`; aux key `aux_B1` → command `set_aux_B1`).

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

## Heat Pump (HPM) Commands

Optional subsystem. Present when a heat pump is paired. Indicated by `heatpump_info.isheatpumpPresent` = `true` in the `get_home` response.

All HPM commands use the same session endpoint.

#### `enable_disable_hpm`

Enable or disable the heat pump.

| Extra param | Value |
|---|---|
| `on_off_action` | `"on"` to enable, `"off"` to disable |

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `serial` | string | Device serial (echoed) |
| `device_status` | string | `"online"` / `"offline"` |
| `is_error` | boolean | Error flag |
| `isHPMPresent` | boolean | Heat pump present |
| `HPMstatus` | string | Operational status string |
| `HPMmode` | string | Current mode |
| `HPMtype` | string | Hardware type |
| `isChillAvailable` | boolean | Chill mode available |
| `poolheatSetPointTemp` | integer | Pool heat set point temperature |
| `spaheatSetPointTemp` | integer | Spa heat set point temperature |
| `response` | string | `"success"` or error string |
| `alert_message` | string | Alert message if any |
| `status` | string | Status string |

#### `switch_hpm_mode`

Switch the heat pump operating mode.

| Extra param | Value |
|---|---|
| `hpm_mode` | Target mode string |

**Response:** Same shape as `enable_disable_hpm`.

#### `setpoint_hpm_temp`

Set pool heat set point, spa heat set point, and/or pool chill set point. Only parameters with values > 0 are sent.

| Extra param | Value |
|---|---|
| `poolheatsetpointtemp` | Pool heat set point (integer, omit if not changing) |
| `spaheatsetpointtemp` | Spa heat set point (integer, omit if not changing) |
| `poolchillsetpointtemp` | Pool chill set point (integer, omit if not changing) |

**Response:** Same shape as `enable_disable_hpm`.

---

## ICL (Intellicenter Light) Commands

Optional subsystem. Present when ICL hardware is paired. Indicated by `is_icl_present` = `"present"` in the `get_home` response.

All ICL commands use the same session endpoint.

#### `get_icl_info`

Read the ICL zone list including zone status, colour, and dimming.

**Common params only** (no extra params).

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `serial` | string | Device serial (echoed) |
| `device_status` | string | `"online"` / `"offline"` |
| `is_error` | string | Error flag |
| `zoneCount` | integer | Number of ICL zones |
| `icl_info_list` | array | List of zone objects (see below) |
| `response` | string | `"success"` or error string |
| `alert_message` | string | Alert message if any |

Each element of `icl_info_list`:

| Field | Type | Description |
|---|---|---|
| `zoneId` | integer | Zone identifier |
| `zoneName` | string | User-assigned zone name |
| `zoneStatus` | string | Zone on/off status string |
| `zoneColor` | integer | Active colour preset index |
| `zoneColorVal` | string | Active colour preset name |
| `dim_level` | integer | Dimming level (0–100) |
| `red_val` | integer | Custom colour red component |
| `green_val` | integer | Custom colour green component |
| `blue_val` | integer | Custom colour blue component |
| `white_val` | integer | Custom colour white component |

#### `onoff_iclzone`

Turn an ICL zone on or off.

| Extra param | Value |
|---|---|
| `zone_id` | Zone identifier (integer) |
| `on_off_action` | `"on"` or `"off"` |

**Response:** Same shape as `get_icl_info`.

#### `set_iclzone_color`

Set the colour preset for an ICL zone.

| Extra param | Value |
|---|---|
| `zone_id` | Zone identifier (integer) |
| `color_id` | Colour preset index (integer, optional — omit to preserve current colour) |
| `dim_level` | Dimming level (integer, 0–100) |

**Response:** Same shape as `get_icl_info`.

**Note:** `color_id` is optional. When omitted, the hardware preserves the zone's current colour and only adjusts brightness. The app uses this same command for both colour selection and brightness-only adjustments; `set_iclzone_dim` exists but is not exercised by any observed UI path.

#### `set_iclzone_dim`

Set the dimming level for an ICL zone.

| Extra param | Value |
|---|---|
| `zone_id` | Zone identifier (integer) |
| `dim_level` | Dimming level (integer, 0–100) |

**Response:** Same shape as `get_icl_info`.

#### `define_iclzone_customcolor`

Set a custom RGBW colour for an ICL zone.

| Extra param | Value |
|---|---|
| `zone_id` | Zone identifier (integer) |
| `red_val` | Red component (integer) |
| `green_val` | Green component (integer) |
| `blue_val` | Blue component (integer) |
| `white_val` | White component (integer) |

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `serial` | string | Device serial (echoed) |
| `device_status` | string | `"online"` / `"offline"` |
| `is_error` | string | Error flag |
| `zone_id` | integer | Zone identifier (echoed) |
| `red_val` | integer | Red value (echoed) |
| `green_val` | integer | Green value (echoed) |
| `blue_val` | integer | Blue value (echoed) |
| `white_val` | integer | White value (echoed) |
| `status` | string | Status string |
| `response` | string | `"success"` or error string |
| `alert_message` | string | Alert message if any |

#### `set_iclzone_name`

Rename an ICL zone.

| Extra param | Value |
|---|---|
| `zone_id` | Zone identifier (integer) |
| `name_val` | New zone name string |

**Response:** Same shape as `get_icl_info`.

#### `enable_disable_zoning_mode`

Enable or disable ICL zoning mode. Also retrieves DCT (Dimmer Control Transmitter) light assignment info.

| Extra param | Value |
|---|---|
| `on_off_action` | `"on"` or `"off"` |

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `serial` | string | Device serial |
| `device_status` | string | `"online"` / `"offline"` |
| `is_error` | boolean | Error flag |
| `zoning_mode_status` | string | Zoning mode status string |
| `DCT_info_list` | array | List of DCT objects (see below) |
| `alert_message` | string | Alert message if any |
| `status` | string | Status string |
| `response` | string | `"success"` or error string |

Each `DCT_info_list` element:

| Field | Type | Description |
|---|---|---|
| `DCTId` | integer | DCT identifier |
| `DCTName` | string | DCT name |
| `DCTSerial` | string | DCT serial number |
| `DCTStatus` | string | DCT status — `"present"` when connected |
| `DCT_light_info` | array | List of light objects on this DCT |

Each `DCT_light_info` element:

| Field | Type | Description |
|---|---|---|
| `lightId` | integer | Light identifier |
| `lightStatus` | string | Light status — `"present"` when connected |
| `lightZone` | integer | Zone this light is assigned to |
| `temperature` | integer | Light temperature (colour temp) |

#### `move_lights_to_zone`

Move a specific light to a different ICL zone.

| Extra param | Value |
|---|---|
| `dct_id` | DCT identifier (integer) |
| `light_id` | Light identifier (integer) |
| `zone_id` | Target zone identifier (integer) |

**Response:** Same shape as `enable_disable_zoning_mode`.

#### `icl_info_list` in `get_devices` response

When an ICL is present, the `get_devices` response contains a top-level `icl_info_list` array (outside `devices_screen`) with abbreviated zone state:

| Field | Type | Description |
|---|---|---|
| `zoneId` | integer | Zone identifier |
| `zoneName` | string | Zone name |
| `zoneStatus` | string | Zone status string |
| `zoneColor` | string | Colour preset (string-encoded integer) |
| `zoneColorVal` | string | Colour preset name |
| `dim_level` | string | Dimming level (string-encoded integer) |

### ICL Enum Wire Values

#### ZoneStatus

| Wire value | Meaning |
|---|---|
| `"on"` | Zone is on |
| `"off"` | Zone is off |
| `"absent"` | Zone has no assigned lights — exclude from display |

Zones with `zoneStatus = "absent"` are not assigned any physical lights and should be excluded from display.

#### ZoneColor (preset index)

The `zoneColor` integer field and the `color_id` parameter for `set_iclzone_color` share the same index space:

| Index | `zoneColorVal` string |
|---|---|
| 0 | `"off"` (no color / zone off) |
| 1 | `"Alpine White"` |
| 2 | `"Sky Blue"` |
| 3 | `"Cobalt Blue"` |
| 4 | `"Caribbean Blue"` |
| 5 | `"Spring Green"` |
| 6 | `"Emerald Green"` |
| 7 | `"Emerald Rose"` |
| 8 | `"Ruby Red"` |
| 9 | `"Magenta"` |
| 10 | `"Violet"` |
| 11 | `"Slow Color Splash"` |
| 12 | `"Fast Color Splash"` |
| 13 | `"America The Beautiful"` |
| 14 | `"Fat Tuesday"` |
| 15 | `"Disco Tech"` |
| 16 | `"Custom Color"` — RGBW values in `red_val`/`green_val`/`blue_val`/`white_val` |

The `zoneColorVal` strings in the response are human-readable display names; they match the index above. When `zoneColor` = 16 (`"Custom Color"`), the RGBW channel fields carry the active color.

---

## VSP (Variable Speed Pump) via iQ20 Session

The iQ20 session endpoint also provides VSP management commands for pumps assigned to aux slots. These are separate from the iQPump `/r-api.iaqualink.net` protocol and operate on pumps physically connected to the iQ20 controller.

All VSP commands use the same session endpoint.

#### `get_vsp_names`

Get names of all VSPs assigned to iQ20 aux slots.

**Common params only** (no extra params).

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `serial` | string | Device serial |
| `device_status` | string | `"online"` / `"offline"` |
| `is_error` | string | Error flag |
| `vsp_names` | array | List of VSP name objects |

Each `vsp_names` element:

| Field | Type | Description |
|---|---|---|
| `pumpId` | integer | VSP slot identifier |
| `pumpName` | string | VSP display name |

#### `get_vsp_speedauxinfo`

Get speed and aux assignment information for a specific VSP slot.

| Extra param | Value |
|---|---|
| `slot_id` | VSP slot identifier (integer) |

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `serial` | string | Device serial |
| `slot_id` | string | VSP slot identifier |
| `device_status` | string | `"online"` / `"offline"` |
| `is_error` | string | Error flag |
| `maxSpeed` | string | Maximum speed |
| `minSpeed` | string | Minimum speed |
| `aux_count` | integer | Number of aux assignments |
| `aux_speed_assignments` | array | List of aux speed assignment strings |
| `vsp_speedInfo` | array | List of speed preset objects |
| `response` | string | `"success"` or error string |

Each `vsp_speedInfo` element:

| Field | Type | Description |
|---|---|---|
| `speedid` | integer | Speed preset identifier |
| `speedName` | string | Speed preset name |
| `speedvalue` | integer | Speed value |
| `enabled` | string | Whether this speed is enabled |

#### `get_vsp_definition`

Get the full VSP definition including master speed settings.

| Extra param | Value |
|---|---|
| `slot_id` | VSP slot identifier (integer) |

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `serial` | string | Device serial |
| `slot_id` | integer | VSP slot identifier |
| `device_status` | string | `"online"` / `"offline"` |
| `is_error` | string | Error flag |
| `vsp_appId` | integer | VSP application ID |
| `vsp_pump_appName` | string | VSP application name |
| `vsp_speed_unit` | string | Speed unit (`"rpm"` or `"gpm"`) |
| `vsp_min_speed` | integer | Minimum speed |
| `vsp_max_speed` | integer | Maximum speed |
| `vsp_model_type` | string | Model type string |
| `vsp_model_typeId` | integer | Model type identifier |
| `vsp_prime_speed` | integer | Priming speed |
| `vsp_prime_duration` | integer | Priming duration |
| `vsp_freeze_protect_speed` | integer | Freeze protection speed |
| `response` | string | `"success"` or error string |

#### `get_vsp_appmodelserials`

Get available VSP application model serial numbers for assignment.

**Common params only** (no extra params).

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `serial` | string | iQ20 serial |
| `device_status` | string | `"online"` / `"offline"` |
| `is_error` | string | Error flag |
| `vsp_app_model_serials` | array | List of available VSP application/model records |
| `response` | string | `"success"` or error string |

Each `vsp_app_model_serials` element:

| Field | Type | Description |
|---|---|---|
| `appId` | integer | Application identifier |
| `appName` | string | Application name |
| `modelName` | string | Model name |
| `modelType` | integer | Model type identifier |
| `pumpId` | integer | Pump slot identifier |
| `pumpSerial` | string | Pump serial number |

#### `get_unassigned_serials`

Get list of unassigned VSP serial numbers available for assignment.

**Common params only** (no extra params).

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `serial` | string | iQ20 serial |
| `device_status` | string | `"online"` / `"offline"` |
| `is_error` | string | Error flag |
| `unassigned_serial_count` | integer | Number of unassigned serials |
| `unassigned_serials` | array | List of unassigned serial number strings |
| `response` | string | `"success"` or error string |

#### `set_vsp_name`

Rename a VSP.

| Extra param | Value |
|---|---|
| `slot_id` | VSP slot identifier (integer) |
| `pump_name` | New pump name string |

**Response:** Not observed — response shape not confirmed from wire traffic.

#### `set_vsp_definition`

Write the full VSP definition (application and speed limits).

| Extra param | Value |
|---|---|
| `slot_id` | VSP slot identifier (integer) |
| `app_id` | Application ID (integer) |
| `model_typeid` | Model type ID (integer) |

**Response:** Not observed — response shape not confirmed from wire traffic.

#### `assign_vsp_serial`

Assign a VSP serial number to an iQ20 aux slot.

| Extra param | Value |
|---|---|
| `slot_id` | Aux slot identifier (integer) |
| `vsp_serial` | VSP serial number string |

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `serial` | string | iQ20 serial |
| `slot_id` | integer | Slot identifier |
| `vsp_assigned_serial` | string | Serial number that was assigned |
| `device_status` | string | `"online"` / `"offline"` |
| `is_error` | string | Error flag |
| `response` | string | `"success"` or error string |
| `status` | string | Status string |

#### `unassign_vsp_serial`

Remove a VSP serial assignment from an iQ20 aux slot.

| Extra param | Value |
|---|---|
| `slot_id` | Aux slot identifier (integer) |

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `serial` | string | iQ20 serial |
| `vsp_unassigned_serial` | string | Serial number that was unassigned |
| `device_status` | string | `"online"` / `"offline"` |
| `is_error` | string | Error flag |
| `response` | string | `"success"` or error string |

#### `enable_disable_pump_speedId`

Enable or disable a specific speed preset for a VSP.

| Extra param | Value |
|---|---|
| `slot_id` | VSP slot identifier (integer) |
| `speed_id` | Speed preset identifier (integer) |
| `on_off_action` | `"on"` or `"off"` |

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `serial` | string | iQ20 serial |
| `slot_id` | integer | VSP slot identifier |
| `unit` | string | Speed unit |
| `vsp_speedInfo` | array | Updated speed preset list |
| `device_status` | string | `"online"` / `"offline"` |
| `is_error` | string | Error flag |
| `response` | string | `"success"` or error string |
| `alert_message` | string | Alert message if any |

Each `vsp_speedInfo` element:

| Field | Type | Description |
|---|---|---|
| `speedId` | integer | Speed preset identifier |
| `speedvalue` | integer | Speed value |
| `status` | string | Enabled status string |

#### `set_aux_speed`

Assign an aux output to a VSP speed preset.

| Extra param | Value |
|---|---|
| `slot_id` | VSP slot identifier (integer) |
| `speed_id` | Speed preset identifier (integer) |
| `aux_id` | Aux slot identifier (integer) |

**Response:** Same shape as `get_vsp_speedauxinfo`.

#### `set_speed_name`

Rename a VSP speed preset.

| Extra param | Value |
|---|---|
| `slot_id` | VSP slot identifier (integer) |
| `speedname_id` | Speed name identifier (integer) |
| `speed_name` | New name string |

**Response:** Not observed — response shape not confirmed from wire traffic.

#### `set_speedname_value`

Set the RPM/GPM value for a named VSP speed preset.

| Extra param | Value |
|---|---|
| `slot_id` | VSP slot identifier (integer) |
| `speedname_id` | Speed name identifier (integer) |
| `speed_value` | Speed value (integer) |

**Response:** Not observed — response shape not confirmed from wire traffic.

#### `enable_pump_speed_value`

Apply a temporary speed change to a VSP.

| Extra param | Value |
|---|---|
| `slot_id` | VSP slot identifier (integer) |
| `speedname_id` | Speed name identifier (integer) |
| `on_off_action` | `"on"` or `"off"` |
| `speed_value` | Speed value (integer) |

**Response:** Same shape as `enable_disable_pump_speedId`.

---

## Scheduling Commands

#### `get_schedule_list`

Get the list of schedules for iQ20 devices.

**Common params only** (no extra params).

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `serial` | string | iQ20 serial |
| `device_status` | string | `"online"` / `"offline"` |
| `is_error` | boolean | Error flag |
| `count` | integer | Number of schedules in this page |
| `totalCount` | integer | Total schedule count |
| `pageNum` | integer | Page number |
| `isNewScheduleAllowed` | boolean | Whether creating additional schedules is permitted |
| `scheduleList` | array | List of schedule objects (see below) |
| `response` | string | `"success"` or error string |

Each `scheduleList` element:

| Field | Type | Description |
|---|---|---|
| `id` | integer | Schedule identifier |
| `deviceId` | integer | Associated device identifier |
| `startHrs` | integer | Start time hours (0–23) |
| `startMins` | integer | Start time minutes |
| `stopHrs` | integer | Stop time hours (0–23) |
| `stopMins` | integer | Stop time minutes |
| `scheduleDays` | string | Days descriptor (e.g. `"All Days"`) |
| `vspId` | integer | Associated VSP identifier (if applicable) |

#### `do_schedule_operation`

Add, edit, or delete an iQ20 schedule.

**Extra params:**

| Param | Value | Required for |
|---|---|---|
| `operation` | `"Add"`, `"Edit"`, or `"Delete"` | All |
| `deviceId` | Device identifier (integer) | Add, Edit |
| `startHrs` | Start time hours (integer, 0–23) | Add, Edit |
| `startMins` | Start time minutes (integer) | Add, Edit |
| `stopHrs` | Stop time hours (integer, 0–23) | Add, Edit |
| `stopMins` | Stop time minutes (integer) | Add, Edit |
| `scheduleDays` | Days descriptor string (e.g. `"All Days"`) | Add, Edit |
| `scheduleId` | Schedule identifier string | Edit, Delete |

**Response:** Same shape as `get_schedule_list`.

---

## Peripheral Device List

#### `get_master_device_list`

Get the list of devices connected to the iQ20.

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `serial` | string | iQ20 serial |
| `device_status` | string | `"online"` / `"offline"` |
| `is_error` | boolean | Error flag |
| `count` | integer | Number of devices in this page |
| `totalCount` | integer | Total device count |
| `listType` | integer | List type identifier |
| `pageNum` | integer | Page number |
| `deviceList` | array | List of device objects |
| `response` | string | `"success"` or error string |

Each `deviceList` element:

| Field | Type | Description |
|---|---|---|
| `id` | integer | Device slot identifier |
| `name` | string | Device name |
| `isVSP` | string | Whether this device is a VSP |

---

## TruSense (pH/ORP) Commands

Optional subsystem. Present when a TruSense chemical sensor is connected to the iQ20 controller.

#### `get_phorp_values`

Get current pH and ORP readings.

| Extra param | Value |
|---|---|
| `unit_id` | Sensor unit identifier (integer) |

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `serial` | string | iQ20 serial |
| `device_status` | string | `"online"` / `"offline"` |
| `is_error` | boolean | Error flag |
| `pH_value` | number | Current pH reading |
| `pH_sensor_status` | string | pH sensor operational status |
| `ORP_value` | integer | Current ORP reading (mV) |
| `ORP_sensor_status` | string | ORP sensor operational status |
| `response` | string | `"success"` or error string |

#### `get_phorp_lastcalibinfo`

Get the last calibration date/info for pH or ORP.

| Extra param | Value |
|---|---|
| `unit_id` | Sensor unit identifier (integer) |

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `serial` | string | iQ20 serial |
| `device_status` | string | `"online"` / `"offline"` |
| `is_error` | boolean | Error flag |
| `unit_id` | integer | Sensor unit identifier (echoed) |
| `is_pH_calibrated` | string | Whether pH is calibrated |
| `is_ORP_calibrated` | string | Whether ORP is calibrated |
| `pH_calibration_date` | object | Last pH calibration date — `day`, `month`, `year` (all integers) |
| `ORP_calibration_date` | object | Last ORP calibration date — `day`, `month`, `year` (all integers) |
| `pHORP_Calibration_Status` | string | Combined calibration status string |
| `ORP_Calibration_Status` | string | ORP-specific calibration status string |
| `response` | string | `"success"` or error string |

#### `get_phorp_calibstatus`

Get the current calibration status.

| Extra param | Value |
|---|---|
| `unit_id` | Sensor unit identifier (integer) |

**Response:** Same shape as `get_phorp_lastcalibinfo`.

#### `do1pointphcalibration`

Start a one-point pH calibration.

| Extra param | Value |
|---|---|
| `unit_id` | Sensor unit identifier (integer) |
| `ph_value` | Target pH value (float) |

#### `do_2point_phcalibration`

Start or step through a two-point pH calibration.

| Extra param | Value |
|---|---|
| `unit_id` | Sensor unit identifier (integer) |
| `step_no` | Calibration step number (integer) |

#### `do_orp_calibration`

Start an ORP calibration.

| Extra param | Value |
|---|---|
| `unit_id` | Sensor unit identifier (integer) |

---

## Enum Wire Values

All enum fields are serialized as strings in JSON.

### `is_error` wire type

The `is_error` field type is **inconsistent across subsystems** — it is a JSON boolean on some commands and a JSON string on others. This is a genuine wire inconsistency, not a documentation error. Parsers must handle both.

| Subsystem / command | `is_error` type |
|---|---|
| SWC (`get_swc_config`, `set_swc_config`, `control_swc_boost`) | boolean |
| HPM `enable_disable_hpm` | boolean |
| HPM `switch_hpm_mode`, `setpoint_hpm_temp` | boolean |
| ICL `enable_disable_zoning_mode` | boolean |
| Master device list (`get_master_device_list`) | boolean |
| Scheduling (`get_schedule_list`, `do_schedule_operation`) | boolean |
| TruSense (`get_phorp_values`, `get_phorp_lastcalibinfo`, `get_phorp_calibstatus`) | boolean |
| ICL `get_icl_info`, `onoff_iclzone`, `set_iclzone_color`, `set_iclzone_dim`, `set_iclzone_name` | string |
| ICL `define_iclzone_customcolor` | string |
| VSP `get_vsp_names`, `get_vsp_speedauxinfo`, `get_vsp_definition`, `get_vsp_appmodelserials`, `get_unassigned_serials` | string |
| VSP `assign_vsp_serial`, `unassign_vsp_serial`, `enable_disable_pump_speedId`, `set_aux_speed`, `enable_pump_speed_value` | string |

### `speedid` vs `speedId` in VSP responses

Two VSP response objects use different casing for a similar field:
- `get_vsp_speedauxinfo` → `vsp_speedInfo` elements use `speedid` (lowercase `i`)
- `enable_disable_pump_speedId` → `vsp_speedInfo` elements use `speedId` (capital `I`)

Both are correct wire field names for their respective response objects.

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

### ToggleBoolean

Used for top-level boolean feature flags (e.g. `onetouch`, `web`):

| Wire value | Meaning |
|---|---|
| `"true"` | Feature enabled |
| `"false"` | Feature disabled |

### TemperatureUnit

| Wire value | Meaning |
|---|---|
| `"F"` | Fahrenheit |
| `"C"` | Celsius |
| `"Unknown"` | Unknown |

### AuxType

Wire values for the `type` field in each aux device:

| Wire value | Meaning |
|---|---|
| `"0"` | Generic/normal aux output |
| `"1"` | Dimmable light |
| `"2"` | Colour light |
| `"3"` | SJVA (sub-jetting valve actuator) |
| `"-1"` | Unknown |

---

## Error Handling

| Condition | Detection | Action |
|---|---|---|
| System offline or in service | `status` field = `"Offline"` or `"Service"` in any response | Raise offline exception |
| Device state NaN | Any `state` value = `"NaN"` in `devices_screen` | Skip devices update; no exception |
| HTTP 401 | Response code | Trigger token refresh, retry once |
| HTTP 429 | Response code | Re-raise throttle exception before broader service exception |
| Other HTTP error | Response code ≠ 200 | Raise service exception |

## SWC (Salt Water Chlorinator)

Optional subsystem. Present when a salt water chlorinator is paired with the iQ20 controller. Indicated by the `swc_info` object appearing in the `get_home` response and/or `swc_set_point` being non-empty.

All SWC commands use the same session endpoint as the rest of the iQ20 protocol:

```
GET https://p-api.iaqualink.net/v2/mobile/session.json
```

### Read fields (from `get_home`)

These fields appear at the top level of the flattened `home_screen` array:

| Field | Type | Description |
|---|---|---|
| `swc_set_point` | string | SWC chlorine output level (percentage, `"0"`–`"100"`) |
| `swc_boost` | string | Boost mode active (Toggle enum: `"0"` = off, `"1"` = on) |
| `swc_low` | string | Low-salt warning flag (Toggle enum: `"0"` = normal, `"1"` = low) |
| `swc_info` | object | SWC sub-status object (see below); present only when SWC is available |
| `pool_salinity` | string | Pool salinity reading |
| `spa_salinity` | string | Spa salinity reading |

### `swc_info` object

Nested object under the flattened `home_screen` key `swc_info`:

| Field | Type | Description |
|---|---|---|
| `isswcPresent` | boolean | SWC hardware is present and paired |
| `swcPoolValue` | integer | Current pool SWC output value (percent) |
| `swcPoolStatus` | string | Pool SWC operational status — see `IaquaSwcStatus` enum |
| `swcSpaValue` | integer | Current spa SWC output value (percent) |
| `swcSpaStatus` | string | Spa SWC operational status — see `IaquaSwcStatus` enum |

### Write commands

#### `get_swc_config`

Read the full SWC configuration including boost state, set points, and boost timer.

**Common params only** (no extra params).

**Response fields:**

| Field | Type | Description |
|---|---|---|
| `serial` | string | Device serial (echoed) |
| `device_status` | string | `"online"` / `"offline"` |
| `is_error` | boolean | Error flag |
| `response` | string | `"success"` or error string |
| `poolSWCSP` | integer | Pool SWC set point (0–100) |
| `spaSWCSP` | integer | Spa SWC set point (0–100) |
| `boostStatus` | string | Boost running state — `"on"`, `"paused"`, or absent/empty when not running |
| `boostHrsVal` | integer | Configured boost duration in hours |
| `remainingBoostHrs` | integer | Remaining boost time — hours component |
| `remainingBoostMins` | integer | Remaining boost time — minutes component |
| `boostMode` | string | Which circuit runs during boost — `"pool"` or `"spillover"` |
| `boostDipSwitch` | string | Boost hardware enable — `"on"` if boost is hardware-enabled, `"off"` otherwise |

#### `set_swc_config`

Set pool and spa SWC output percentages (chlorine production level).

**Extra params:**

| Param | Value |
|---|---|
| `poolswcsp` | Pool SWC set point integer (0–100) |
| `spaswcsp` | Spa SWC set point integer (0–100) |

**Response:** Same shape as `get_swc_config`.

#### `control_swc_boost`

Start, stop, pause, or resume boost mode. Also used to configure the boost timer and circuit selection before starting.

**Extra params:**

| Param | Value |
|---|---|
| `boosthrs` | Boost duration in hours (integer, 1–24) |
| `boostmode` | Circuit to run during boost — `"pool"` or `"spillover"` |
| `boostcontrol` | Boost action — `"start"`, `"stop"`, `"pause"`, or `"resume"` |

**Response:** Same shape as `get_swc_config`.

### SWC Enum Wire Values

#### boostStatus

| Wire value | Meaning |
|---|---|
| `"on"` | Boost is actively running |
| `"paused"` | Boost timer is paused |
| `""` (absent/empty) | Boost is not running |

#### boostMode

| Wire value | Meaning |
|---|---|
| `"pool"` | Pool circuit runs during boost |
| `"spillover"` | Spillover (spa spillover) circuit runs during boost |

#### boostcontrol

| Wire value | Meaning |
|---|---|
| `"start"` | Start boost with the configured `boosthrs` and `boostmode` |
| `"stop"` | Cancel/stop a running boost |
| `"pause"` | Pause a running boost timer |
| `"resume"` | Resume a paused boost timer |

#### boostDipSwitch

| Wire value | Meaning |
|---|---|
| `"on"` | Boost is hardware-enabled (DIP switch in enable position) |
| `"off"` (or absent) | Boost is hardware-disabled |

### `IaquaSwcStatus` enum

Wire values for `swcPoolStatus` / `swcSpaStatus`:

| Wire value | Meaning |
|---|---|
| `"standby"` | SWC is idle, not producing chlorine |
| `"running"` | SWC is actively producing chlorine |
| `"boosting"` | SWC is running in boost mode |
| `"boostpaused"` | Boost mode is paused |
| other non-empty string (e.g. `"offline"`) | Unrecognised — treat as unknown status |

### Not Observed / Needs Verification

| # | Item |
|---|---|
| 1 | `boosthrs` upper bound — client enforces max 24 hours; server-side limit unconfirmed |
| 2 | Whether `get_swc_config` response always includes all boost fields, or omits them when no SWC is present |
| 3 | `swc_set_point` in `get_home` vs `poolSWCSP`/`spaSWCSP` in `get_swc_config` — relationship unconfirmed (may be the same value or derived differently) |

---

## Not Observed / Needs Verification (General)

| # | Item |
|---|---|
| 1 | `relay_count` — present in real-world `get_home` fixtures; not found in protocol analysis of model sources. Likely a wire field passed through transparently. |
| 2 | `set_onetouch` write command — `get_onetouch` read is confirmed; no `set_onetouch` command string found in protocol analysis. One Touch preset activation may use a different mechanism. |
| 3 | VSP commands via iQ20 session — confirmed via protocol analysis; exact wire behavior on multi-board configurations needs real-world verification. |
| 4 | TruSense `unit_id` valid range and format — integer confirmed from request signatures; valid range not confirmed from live traffic. |
| 5 | HPM `on_off_action` values for `enable_disable_hpm` — `"on"` / `"off"` inferred; not confirmed from live traffic. |

---

## See Also

- [Implementation Notes: iAqua](../../implementation/systems/iaqua.md) — status lifecycle, design decisions, accepted divergences from this spec
