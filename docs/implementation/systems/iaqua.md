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

## Implemented vs Reference Coverage

### Commands implemented

| Command | Status |
|---|---|
| `get_home` | ✓ Full parse |
| `get_devices` | ✓ Full parse |
| `get_onetouch` | ✓ Full parse |
| `set_pool_pump`, `set_spa_pump` | ✓ |
| `set_pool_heater`, `set_spa_heater`, `set_solar_heater` | ✓ |
| `set_aux_{n}` | ✓ |
| `set_light` | ✓ |
| `set_temps` | ✓ |
| `set_onetouch_{n}` | ✓ |

### `get_home` response fields not tracked as devices

The following fields appear in the reference `get_home` response but are not currently parsed into `self.devices`:

| Field | Notes |
|---|---|
| `swc_set_point` | SWC not yet implemented (see below) |
| `swc_boost` | SWC not yet implemented |
| `swc_low` | SWC not yet implemented |
| `swc_info` object | SWC sub-status; not yet parsed |
| `heatpump_info` object | HPM sub-status; not yet parsed |
| `acl_value` | ACL sensor; not yet parsed |
| `lockedout_message` | Informational string; not parsed |

`icl_info_list` in the `get_devices` response is also not parsed.

### Unimplemented subsystems

#### SWC (Salt Water Chlorinator)

Commands `get_swc_config`, `set_swc_config`, and `control_swc_boost` are documented in the reference but not implemented in master. The `swc_info` nested object from `get_home` is not parsed. Implementation is in progress on a separate branch.

Devices that will be exposed when implemented: `swc_set_point` (sensor), `swc_pool_set_point` (writable), `swc_spa_set_point` (writable), `swc_boost`, `swc_low`, `swc_pool_value`, `swc_pool_status`, `swc_spa_value`, `swc_spa_status`, and several boost timer/config sensors.

#### Heat Pump (HPM)

Commands `enable_disable_hpm`, `switch_hpm_mode`, and `setpoint_hpm_temp` are not implemented. The `heatpump_info` nested object from `get_home` is not parsed, so heat pump operational status (`heatpumpstatus`, `heatpumpmode`, `heatpumptype`) is not tracked.

`pool_chill_set_point` from `get_home` is not tracked. Writing the chill set point requires `setpoint_hpm_temp` (HPM command), which is not yet implemented.

#### ICL (Intellicenter Light)

Zone control commands (`get_icl_info`, `onoff_iclzone`, `set_iclzone_color`, `set_iclzone_dim`, `define_iclzone_customcolor`, `set_iclzone_name`, `enable_disable_zoning_mode`, `move_lights_to_zone`) are not implemented. `icl_info_list` from `get_devices` is not parsed.

`is_icl_present` from `get_home` is tracked as `IaquaPresenceSensor`, so ICL hardware presence is detectable.

#### VSP via iQ20 Session

The iQ20 session endpoint hosts 14 VSP management commands (`get_vsp_names`, `get_vsp_speedauxinfo`, `get_vsp_definition`, `get_vsp_appmodelserials`, `get_unassigned_serials`, `set_vsp_name`, `set_vsp_definition`, `assign_vsp_serial`, `unassign_vsp_serial`, `enable_disable_pump_speedId`, `set_aux_speed`, `set_speed_name`, `set_speedname_value`, `enable_pump_speed_value`). None are implemented.

Note: these iQ20-session VSP commands are distinct from the iQPump protocol handled by the `i2d` system. They control pumps physically wired to the iQ20 controller via the same `p-api` session endpoint.

#### TruSense (pH/ORP Calibration)

`orp` and `ph` sensor readings are already parsed from `get_home` and exposed as `IaquaSensor` devices. However, the TruSense calibration commands (`get_phorp_values`, `get_phorp_lastcalibinfo`, `get_phorp_calibstatus`, `do1pointphcalibration`, `do_2point_phcalibration`, `do_orp_calibration`) are not implemented.

#### Scheduling

`get_schedule_list` and `do_schedule_operation` are not implemented.

#### Peripheral Device List

`get_master_device_list` is not implemented.

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

### Virtual thermostat devices

`pool_thermostat` and `spa_thermostat` do not appear in any wire response. They are synthesised by `_parse_home_response` when both the matching `{prefix}_set_point` (Number) and `{prefix}_heater` (Switch) are present. This gives callers a single `IaquaClimate` object aggregating the set point, heater state, and temperature sensor — matching the HA climate platform contract without extra network calls.

### Authorization header format

The reference app sends the `IdToken` bare (no `Bearer` prefix) in the `Authorization` header on session requests. The current Python implementation sends `Bearer {id_token}`. This diverges from the reference but works against the production API.

## Deltas vs Protocol Reference

Only genuine divergences are listed here. The following reference behaviors all match the current implementation and are not listed:

- **Session host** — implementation uses `p-api.iaqualink.net` (matches reference). An earlier version of this doc incorrectly listed `r-api`; that was a documentation error.
- **`get_home` extra params** — implementation sends both `country` and `attached_test=true` (matches reference).

| # | Observed reference | Current Python (`IaquaSystem`) |
|---|---|---|
| 1 | `Authorization` header: bare `{IdToken}` (no prefix) | Sends `Bearer {id_token}` |

## See Also

- [Protocol Reference: iAqua](../../reference/systems/iaqua.md) — wire-level spec
- [API Reference: iAqua](../../api/systems/iaqua.md) — class and method docs
