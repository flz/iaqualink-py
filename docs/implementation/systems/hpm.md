# HPM Implementation Notes

Implementation details for hpm systems (`device_type: "hpm"` — standalone heat-pump-only WiFi modules, not attached to an `iaqua` pool controller). For the wire-level protocol, see [Protocol Reference: hpm](../../reference/systems/hpm.md).

## Overview

| Property | Value |
|----------|-------|
| `device_type` | `hpm` |
| API host | `prod.zodiac-io.com` |
| Authentication | JWT `IdToken` (bare, no `Bearer` prefix) |
| Update call | Single shadow state fetch (`GET /devices/v1/{serial}/shadow`) |
| Write commands | `POST` to the same shadow URL with a `{"state": {"desired": {...}}}` body |
| Python class | `HpmSystem` in `src/iaqualink/systems/hpm/system.py` |

## System Status Lifecycle

Identical mechanism to `exo`: status is read directly from `state.reported.aws.status`
and mapped through the same string→`SystemStatus` table (`connected`, `online`,
`offline`, `disconnected`, `service`, `firmware_update`; anything else or absent →
`unknown`).

### `_refresh()` template

1. Issue `GET /devices/v1/{serial}/shadow` with `Authorization: {id_token}`.
2. Call `_parse_shadow_response()`:
   - Map `state.reported.aws.status` to `self.status`.
   - Extract `state.reported.equipment.hp_0`. If absent, leave `self.devices` untouched
     and return (no error — an account can be online with no equipment block yet).
3. Build/update the device registry (see §Device Model below) from that one block.

`refresh()` in the base class resets status to `IN_PROGRESS` before calling
`_refresh()`.

## Device Model

Unlike `exo`, which flattens each `equipment.swc_0` key into its own device, `hp_0` on
this system is a single nested block containing everything for the one heat pump
(index 0 — no evidence multi-unit hpm accounts exist). `_parse_shadow_response` splits
it into named devices by *role* rather than by wire key, since several devices need the
same underlying `hp_0` dict (e.g. `heatpump`, `mode`, and `cooling_priority` all read
from the same block, just different keys within it).

### Device registry

| Device key | Source | Class |
|---|---|---|
| `heatpump` | `hp_0` (`state`, `tsp`) | `HpmHeatPump` |
| `mode` | `hp_0.st` | `HpmMode` |
| `cooling_priority` | `hp_0.cl` | `HpmCoolingPriority` |
| `status` | `hp_0.status` | `HpmOperatingStatusSensor` |
| `reason` | `hp_0.reason` | `HpmStandbyReasonSensor` |
| `water_temp` | `hp_0.sns_1` | `HpmWaterTemperature` |
| `air_temp` | `hp_0.sns_2` | `HpmAirTemperature` |
| `water_flow` | `hp_0.wf` | `HpmWaterFlow` |

`HpmHeatPump.current_temperature` reads the sibling `water_temp` device rather than
carrying its own copy of the sensor value — the same cross-device-reference pattern
`ExoClimate` uses to read its water-temp sensor.

### Fields with no device

`_parse_shadow_response` builds a fixed set of device keys, so unlike `exo` — which
iterates whatever keys the wire sends — a field with no entry above is simply not
surfaced. Several are present on the wire but not understood well enough to model
(`tmp`, `led`, `compressorSpeed`, `errorCode`, `errorTime`); adding one means adding it
to both the parse step and `HpmDevice.from_data`. `HpmAttributeSensor` exists as a
fallback so `from_data` stays total for direct callers, but nothing reaches it through
a normal refresh.

### `hp` is left to the app

`hp` ("Heating Priority") is the only writable `hp_0` field with no device class and no
write method. Exercising it needs a dry contact wired to the unit, which no available
unit had, and the app refuses to write it while `ty` is `"UNK"` — so its behaviour
could not be checked end to end. Adding it later means a switch device plus a
`set_heating_priority()`, mirroring `cl`. See the `hp` and `ty` rows in the
[protocol reference](../../reference/systems/hpm.md).

## Write Path

All writes go through `send_desired_state_request`, identical in shape to `exo`'s
`send_desired_state_request` — a `POST` to the same shadow URL with
`{"state": {"desired": {...}}}`.

Every write is subject to the propagation delay described in the [protocol
reference](../../reference/systems/hpm.md): the unit can take upwards of 15 seconds to
apply a change and report it back, so a refresh straight after a write usually still
reads the old value.

| Method | Target field |
|---|---|
| `set_state(state)` | `hp_0.state` |
| `set_setpoint(temperature)` | `hp_0.tsp` |
| `set_mode(mode)` | `hp_0.st` |
| `set_cooling_priority(enabled)` | `hp_0.cl` |

There is no `set_heating_priority()` for `hp_0.hp` — see
[below](#hp-is-left-to-the-app).

## Design Decisions

### Modeled as a Climate entity, matching the library's existing heat-pump precedent

`iaqua` already has a heat pump sub-device pattern (on/off switch + mode select +
set point, paired to a full pool controller). This standalone system reuses the same
device-type shapes (`AqualinkClimate` for on/off + set point, `AqualinkSelect` for mode)
rather than inventing a new base device type, per the "only add a new base device type
when meaningfully different" guidance in
[Adding a New Base Device Type](../../contributing/new-device-type.md).

### `status` exposed as a separate diagnostic sensor, not folded into the Climate entity

`AqualinkClimate` only has `is_on`/`turn_on`/`turn_off` — no generic multi-value
hvac-mode concept. Rather than stretch that interface, the richer 4-value `status`
(off/standby/heating/cooling) is exposed as its own `HpmOperatingStatusSensor` with an
`IntEnum` translation via `AqualinkSensor.value_enum`.

### Conservative, explicitly-flagged set-point bounds

The API reports no min/max fields for `tsp` anywhere in the observed schema (`exo`, by
contrast, has explicit `sp_min`/`sp_max`). `HpmHeatPump.min_temp`/`max_temp` are a
placeholder range wide enough not to reject a real set point, not a confirmed device
limit — flagged in code comments and in the [protocol reference](../../reference/systems/hpm.md).

## Deltas vs Protocol Reference

None at present.

## See Also

- [Protocol Reference: hpm](../../reference/systems/hpm.md) — wire-level spec, including per-field confidence notes
- [API Reference: hpm](../../api/systems/hpm.md) — class and method docs
