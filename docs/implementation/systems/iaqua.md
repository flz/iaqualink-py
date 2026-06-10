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

### Unimplemented subsystems

#### SWC (Salt Water Chlorinator)

Commands `get_swc_config`, `set_swc_config`, and `control_swc_boost` are documented in the reference but not implemented in master. The `swc_info` nested object from `get_home` is not parsed. Implementation is in progress on a separate branch.

Devices that will be exposed when implemented: `swc_set_point` (sensor), `swc_pool_set_point` (writable), `swc_spa_set_point` (writable), `swc_boost`, `swc_low`, `swc_pool_value`, `swc_pool_status`, `swc_spa_value`, `swc_spa_status`, and several boost timer/config sensors.

#### Heat Pump (HPM)

Commands `enable_disable_hpm`, `switch_hpm_mode`, and `setpoint_hpm_temp` are not implemented. The `heatpump_info` nested object from `get_home` is not parsed, so heat pump operational status (`heatpumpstatus`, `heatpumpmode`, `heatpumptype`) is not tracked.

`pool_chill_set_point` from `get_home` is not tracked. Writing the chill set point requires `setpoint_hpm_temp` (HPM command), which is not yet implemented.

#### VSP via iQ20 Session

The iQ20 session endpoint hosts 14 VSP management commands. Of these, `get_vsp_names`, `get_vsp_speedauxinfo`, `enable_disable_pump_speedId`, `get_vsp_appmodelserials`, and `get_master_device_list` are implemented (see [VSP Pump Control](#vsp-pump-control) below). The remaining 9 management commands (`get_vsp_definition`, `get_unassigned_serials`, `set_vsp_name`, `set_vsp_definition`, `assign_vsp_serial`, `unassign_vsp_serial`, `set_aux_speed`, `set_speed_name`, `set_speedname_value`, `enable_pump_speed_value`) are not implemented.

Note: these iQ20-session VSP commands are distinct from the iQPump protocol handled by the `i2d` system. They control pumps physically wired to the iQ20 controller via the same `p-api` session endpoint.

#### TruSense (pH/ORP Calibration)

`orp` and `ph` sensor readings are already parsed from `get_home` and exposed as `IaquaSensor` devices. However, the TruSense calibration commands (`get_phorp_values`, `get_phorp_lastcalibinfo`, `get_phorp_calibstatus`, `do1pointphcalibration`, `do_2point_phcalibration`, `do_orp_calibration`) are not implemented.

#### Scheduling

`get_schedule_list` and `do_schedule_operation` are not implemented.

#### Peripheral Device List

`get_master_device_list` is implemented and used during VSP pump discovery (see [VSP Pump Control](#vsp-pump-control)).

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

## VSP Pump Control

### Overview

Variable-speed pump support is an optional subsystem within `IaquaSystem`. It is entirely separate from the standalone Jandy iQPump (device type `i2d`). All VSP commands use the same session endpoint as the rest of the iQ20 protocol (`p-api.iaqualink.net/v2/mobile/session.json`).

### Device class

`IaquaPump(AqualinkFan, IaquaDevice)` — inherits device identity from `IaquaDevice` and exposes the `AqualinkFan` preset contract (suitable for a Home Assistant `fan` entity).

| `AqualinkFan` property | `IaquaPump` behaviour |
|---|---|
| `supports_turn_on` | `True` — activates first speed preset (or `speed_id=1` if presets not yet loaded) via `enable_disable_pump_speedId` |
| `supports_turn_off` | `True` — sends `enable_disable_pump_speedId` with `on_off_action=off` |
| `supports_presets` | `True` after `fetch_speed()` is called; always `True` post-discovery since `fetch_speed()` runs before device enters `self.devices` |
| `preset_modes` | Raises `AqualinkOperationNotSupportedException` if `_speed_presets` not yet populated |
| `preset_mode` | Raises same exception if not loaded; returns `None` if no preset has `enabled == "true"` |
| `supports_percentage` | `False` — arbitrary-RPM write not yet confirmed for iaqua VSP |

### Slot ID

Each VSP pump is identified by a `slot_id` (integer). This is stored in `device.data["slot_id"]` and read via `IaquaPump.slot_id`. It is set during discovery and passed to all speed commands.

### Discovery flow

`_refresh_vsp_pumps()` runs **once per system lifetime** (guarded by `_vsp_discovered`):

1. Check `system.data.get("isVSP") == "true"` (`is_vsp` property) — skip if false.
2. Call `get_vsp_names()` → build `pumpId → pumpName` map.
3. Call `get_master_device_list()` → filter to `isVSP == "true"` entries; if none found, fall back to `get_vsp_appmodelserials()`.
4. For each slot ID not already in `self.devices`: create `IaquaPump`, call `fetch_speed()` to populate `_speed_presets`, then add to `self.devices`.

Called from `_refresh()` after `_parse_devices_response`, only when `is_vsp and not _vsp_discovered`. The pump is never added to `self.devices` before `_speed_presets` is populated.

### Preset lifecycle

```python
# _speed_presets populated automatically during _refresh_vsp_pumps() discovery
pump.preset_modes               # ["LO", "MED", "HI", ...]
pump.preset_mode                # name of preset with enabled=="true", or None
await pump.set_preset_mode("LO")  # calls enable_disable_pump_speedId; updates _speed_presets from response
await pump.turn_off()             # calls enable_disable_pump_speedId with on_off_action=off
await pump.fetch_speed()          # explicit refresh from get_vsp_speedauxinfo if needed
```

`_speed_presets` is populated by `fetch_speed()` during discovery. After each write (`set_preset_mode`, `turn_on`, `turn_off`), `_apply_speed_update()` merges the response `vsp_speedInfo` back into `_speed_presets` so `is_on` and `preset_mode` stay current without an extra round-trip. Callers needing a full refresh can call `fetch_speed()` explicitly.

### Design decisions

**`supports_presets` is `True` after `fetch_speed()`:** `IaquaPump` is always a VSP-capable device (that's why it was created). In practice `fetch_speed()` runs during discovery before the device enters `self.devices`, so by the time any external caller sees the pump `supports_presets` is already `True`. `False` is only observable if `IaquaPump` is constructed directly without calling `fetch_speed()`.

**No automatic preset refresh on `_refresh()`:** `get_vsp_speedauxinfo` is an extra HTTP call per pump. The current active preset can change externally (e.g. schedule), so callers needing up-to-date preset state should call `fetch_speed()` explicitly.

**`slot_id` in `data`, not constructor:** Keeps the `IaquaDevice` constructor signature uniform (`system, data`). Discovery stores `slot_id` in the data dict; `IaquaPump.slot_id` reads it with a default of `1`.

**Turn on/off via `enable_disable_pump_speedId`:** `turn_on` activates the first configured speed preset (or `speed_id=1` if presets unavailable). `turn_off` sends `on_off_action=off` via `stop_vsp_pump()`. Both update `_speed_presets` via `_apply_speed_update()` from the response.

### Deltas vs Protocol Reference

| # | Reference spec | Current implementation |
|---|---|---|
| 1 | `get_master_device_list` used to enumerate VSP devices with `isVSP` flag | ✓ Called during discovery; per-device `isVSP` flag is the primary slot-ID source. Falls back to `get_vsp_appmodelserials` if master list returns no VSP devices. |
| 2 | `get_vsp_speedauxinfo` response uses `slot` (not `slot_id`) | Parsed via `data.get("vsp_speedInfo", [])` — `slot` field not consumed |
| 3 | `enable_disable_pump_speedId` response carries updated `vsp_speedInfo` with `status` values | ✓ Parsed by `_apply_speed_update()` after `turn_on`, `turn_off`, and `set_preset_mode` |
| 4 | `get_vsp_names` / `get_vsp_appmodelserials` called once at discovery | ✓ Matches — guarded by `_vsp_discovered` flag |
| 5 | Arbitrary-RPM write command exists (path observed, shape unconfirmed) | Not implemented — `supports_percentage` returns `False` |

## See Also

- [Protocol Reference: iAqua](../../reference/systems/iaqua.md) — wire-level spec
- [API Reference: iAqua](../../api/systems/iaqua.md) — class and method docs
