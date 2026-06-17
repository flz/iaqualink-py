# iAqua Implementation Notes

Implementation details for the iAqua system (`device_type: "iaqua"`). For the wire-level protocol, see [Protocol Reference: iAqua](../../reference/systems/iaqua.md).

## Overview

| Property | Value |
|----------|-------|
| `device_type` | `iaqua` |
| API host | `p-api.iaqualink.net` |
| Authentication | Session token (`session_id`) + Bearer `IdToken` |
| Update calls | `get_home` + `get_devices` (+ `get_onetouch` if supported); ICL state embedded in `get_devices` |
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
| `onoff_iclzone`, `set_iclzone_color`, `define_iclzone_customcolor` | ✓ (ICL) |
| `enable_disable_hpm`, `switch_hpm_mode`, `setpoint_hpm_temp` | ✓ (HPM) |

### `get_home` response fields not tracked as devices

The following fields appear in the reference `get_home` response but are not currently parsed into `self.devices`:

| Field | Notes |
|---|---|
| `swc_set_point` | SWC not yet implemented (see below) |
| `swc_boost` | SWC not yet implemented |
| `swc_low` | SWC not yet implemented |
| `swc_info` object | SWC sub-status; not yet parsed |
| `acl_value` | ACL sensor; not yet parsed |
| `lockedout_message` | Informational string; not parsed |

### Unimplemented subsystems

#### SWC (Salt Water Chlorinator)

Commands `get_swc_config`, `set_swc_config`, and `control_swc_boost` are documented in the reference but not implemented in master. The `swc_info` nested object from `get_home` is not parsed. Implementation is in progress on a separate branch.

Devices that will be exposed when implemented: `swc_set_point` (sensor), `swc_pool_set_point` (writable), `swc_spa_set_point` (writable), `swc_boost`, `swc_low`, `swc_pool_value`, `swc_pool_status`, `swc_spa_value`, `swc_spa_status`, and several boost timer/config sensors.

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

## ICL (IntelliCenter Light) Sub-System

ICL is an optional iQ20 sub-system providing per-zone RGBW LED control. For the wire-level protocol see the [ICL section of the Protocol Reference](../../reference/systems/iaqua.md#icl-intellicenter-light-sub-system).

### Overview

| Property | Value |
|---|---|
| Detection | `is_icl_present` device (`IaquaPresenceSensor`) in `self.devices`; ICL zones auto-created from `icl_info_list` in `get_devices` |
| Python class | `IaquaIclLight` (`src/iaqualink/systems/iaqua/device.py`) |
| Device key format | `icl_zone_{zoneId}` (e.g. `icl_zone_1`) |
| State enum | `IaquaZoneStatus` — `ON`/`OFF`/`ABSENT` |

### Device Lifecycle

ICL zones are parsed from `icl_info_list` embedded in the `get_devices` response (see [state source](#icl-state-source-embedded-icl_info_list-vs-get_icl_info) below). Zones with `zoneStatus = "absent"` are skipped and never added to `self.devices`. The remaining zones are upserted by key on every `_parse_devices_response` call.

After write commands that return the full `icl_info_list` shape (`onoff_iclzone`, `set_iclzone_color`), state is refreshed via `_parse_icl_info_response`. The `define_iclzone_customcolor` response uses a narrower shape (no `icl_info_list`); `_parse_icl_custom_color_response` handles it by patching only the RGBW channel fields on the affected device.

### State Model

`IaquaIclLight.state` returns the raw `zoneStatus` wire value. `state_enum` is `IaquaZoneStatus`:

| `IaquaZoneStatus` | Wire value | `is_on` |
|---|---|---|
| `ON` | `"on"` | `True` |
| `OFF` | `"off"` | `False` |
| `ABSENT` | `"absent"` | filtered at parse time — not a device |

### Property → Wire Field Mapping

| Property | Wire field(s) | Notes |
|---|---|---|
| `label` | `zoneName` | Falls back to `"Light Zone {_zone_id}"` if empty |
| `state` | `zoneStatus` | Raw wire value |
| `is_on` | `zoneStatus` | `== IaquaZoneStatus.ON` |
| `brightness_percentage` | `dim_level` | `int`, 0–100; `None` if field absent |
| `effect` | `zoneColorVal` | Human-readable name string; `None` if empty |
| `_color_id` | `zoneColor` | Integer 0–16; internal — not part of `AqualinkLight` API |
| `rgbw` | `red_val`, `green_val`, `blue_val`, `white_val` | 4-tuple; defaults to `(0, 0, 0, 0)` if fields absent |

### Operations

| Method | Command | Notes |
|---|---|---|
| `turn_on()` | `onoff_iclzone` | Noop if already on |
| `turn_off()` | `onoff_iclzone` | Noop if already off |
| `set_brightness_percentage(0–100)` | `set_iclzone_color` | See brightness command decision below |
| `set_effect(name)` | `set_iclzone_color` | Validated by base class; dispatches via `_set_effect()` |
| `_set_effect_by_id(id)` | `set_iclzone_color` | Internal; validates against `ICL_EFFECTS` values |
| `set_rgbw(r, g, b, w=0)` | `define_iclzone_customcolor` | Each channel 0–255 |

### Design Decisions

#### ICL state source: embedded `icl_info_list` vs `get_icl_info`

Zone state is read from `icl_info_list` embedded in the `get_devices` response rather than via a separate `get_icl_info` call. The `get_icl_info` endpoint is not called for three reasons:

1. **Redundant data** — `icl_info_list` embedded in `get_devices` contains the same per-zone fields; no zone data is lost.
2. **Timeout** — a separate `get_icl_info` call times out on some hardware in the field.
3. **Unused envelope** — `get_icl_info` additionally returns `alert_message`, `device_status`, `is_error`, and `zoneCount`; none are used by this implementation.

#### ICL brightness command: `set_iclzone_color` not `set_iclzone_dim`

`icl_set_brightness` uses `set_iclzone_color`, not `set_iclzone_dim`. The app uses `set_iclzone_color` for both color selection and brightness-only changes; `set_iclzone_dim` exists in the app source but is not called from any observed app UI path.

#### ICL brightness step validation: 5% increments

The API accepts any integer in 0–100 for `dim_level`. The implementation rejects non-multiples of 5 because the app only exposes 5% increments in its UI (0, 5, 10, …, 100). This is an app-level constraint, not a wire-level one.

### Deltas vs Protocol Reference (ICL)

| # | Reference behaviour | Python implementation |
|---|---|---|
| 1 | `get_icl_info` for zone state polling | Not called — zone data read from `get_devices` embedded `icl_info_list`; see design decision above |
| 2 | `is_icl_present` = `"present"` signals ICL presence | ✓ Matches |
| 3 | Absent zones excluded from display | ✓ Filtered at parse time; absent zones are never added to `self.devices` |
| 4 | Brightness via `set_iclzone_color` | ✓ Matches; `set_iclzone_dim` not used |
| 5 | `define_iclzone_customcolor` returns a narrower response (no `icl_info_list`) | ✓ Handled by `_parse_icl_custom_color_response` |
| 6 | Color preset index 16 = custom RGBW mode (not a named preset) | ✓ `ICL_EFFECTS` covers indices 0–15; index 16 not exposed as a named effect — use `set_rgbw()` instead |

## HPM (Heat Pump) Sub-System

HPM is an optional iQ20 sub-system controlling a heat pump paired with the controller — distinct from the simple relay-based `pool_heater`/`spa_heater`/`solar_heater` toggles, and distinct from the standalone AWS-IoT-shadow-based heat pump device (a different, unrelated subsystem). For the wire-level protocol see the [HPM section of the Protocol Reference](../../reference/systems/iaqua.md#heat-pump-hpm-commands).

### Overview

| Property | Value |
|---|---|
| Detection | `heatpump_info.isheatpumpPresent` in `get_home`, or `isHPMPresent` echoed by any HPM write command |
| Python classes | `IaquaHeatPump` (switch), `IaquaHeatPumpMode` (select), `IaquaHeatPumpStatusSensor`, `IaquaHeatPumpAlertSensor` (`src/iaqualink/systems/iaqua/device.py`) |
| Device keys | `heatpump`, `heatpump_mode`, `heatpump_status`, `heatpump_alert` |
| Enums | `IaquaHpmMode` (`HEAT`/`CHILL`), `IaquaHpmStatus` (`OFF`/`ENABLED`/`ON`), `IaquaHpmErrorCode` (`src/iaqualink/systems/iaqua/enums.py`) |

### Device Lifecycle

All four devices are upserted together by `IaquaSystem._upsert_heatpump()`, fed from two different shapes of the same underlying data:

- `get_home`'s `heatpump_info` object (lowercase keys: `isheatpumpPresent`, `heatpumpstatus`, `heatpumpmode`, `heatpumptype`, `isChillAvailable`) — polled on every `refresh()`.
- The echoed response from any of the three HPM write commands (`HPMxxx`-cased keys, plus `alert_message` — see below).

`heatpump` and `heatpump_status` are created whenever the heat pump is present. `heatpump_mode` is only created when `isChillAvailable` is true — there's no real choice to offer otherwise, matching the gating already used elsewhere in this system (e.g. ICL zones, OneTouch). `heatpump_alert` is only created once an HPM write-command response has actually supplied `alert_message` — that field is **not** part of `get_home`'s `heatpump_info` shape (not observed in reference there), so a freshly-discovered heat pump has no alert sensor until the first command response arrives. If the heat pump is unpaired (`isheatpumpPresent`/`isHPMPresent` becomes false, or `heatpump_info` disappears from `get_home` entirely), all four devices are removed — mirroring the existing ICL zone `ABSENT` removal behavior.

There is no dedicated read-only HPM status command — confirmed from the reference, only `get_home` polling and the three write commands' echoes ever carry HPM status.

### Operations

| Method | Command | Notes |
|---|---|---|
| `IaquaHeatPump.turn_on()` / `turn_off()` | `enable_disable_hpm` | Noop if already in the target state |
| `IaquaHeatPumpMode.select_option("heat"\|"chill")` | `switch_hpm_mode` | Validated against `options` by the base `AqualinkSelect` template method |
| `pool_set_point.set_value()` / `spa_set_point.set_value()` / `pool_chill_set_point.set_value()` | `setpoint_hpm_temp` | See routing decision below |

### Design Decisions

#### `pool_set_point`/`spa_set_point` route through `setpoint_hpm_temp` when a heat pump is paired

`pool_set_point` and `spa_set_point` are the same logical target temperature regardless of which equipment is doing the heating. When no heat pump is paired, writing them sends `set_temps` (`temp1`/`temp2`), as before. When a heat pump **is** paired (`"heatpump" in self.devices`), the heat pump becomes the equipment that actually heats, so writes are sent via `setpoint_hpm_temp` (`poolheatsetpointtemp`/`spaheatsetpointtemp`) instead. This is a behavior change for any existing user with a heat pump-equipped system — `IaquaClimate` (the composed pool/spa thermostat) needed no code changes, since it already delegates to the set point's `set_value()`. `pool_chill_set_point` has no relay-heater equivalent and always routes through `setpoint_hpm_temp` (`poolchillsetpointtemp`).

#### Reused temperature bounds for HPM set points

`pool_chill_set_point` reuses the same `IAQUA_TEMP_*_LOW`/`HIGH` bounds as the relay-heater set points. No HPM-specific bounds were found in the reference — not observed.

### Deltas vs Protocol Reference (HPM)

| # | Reference behaviour | Python implementation |
|---|---|---|
| 1 | `on_off_action` literal `"on"`/`"off"` for `enable_disable_hpm` | ✓ Matches |
| 2 | `setpoint_hpm_temp` only sends the parameter(s) being changed | ✓ Matches — no seeding of unrelated set points, unlike `set_temps` |
| 3 | No HPM-specific temperature bounds documented | Reuses relay-heater bounds (assumption, not observed in reference) |

## See Also

- [Protocol Reference: iAqua](../../reference/systems/iaqua.md) — wire-level spec
- [API Reference: iAqua](../../api/systems/iaqua.md) — class and method docs
