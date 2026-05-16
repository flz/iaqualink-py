# i2d Implementation Notes

Implementation details for i2d systems (`device_type: "i2d"` — iQPump variable-speed pump controllers). For the wire-level protocol, see [Protocol Reference: i2d](../reference/i2d.md).

## Overview

| Property | Value |
|----------|-------|
| `device_type` | `i2d` |
| API host | `r-api.iaqualink.net` |
| Authentication | Bearer `IdToken` + `api_key` header |
| Update call | `POST /v2/devices/{serial}/control.json` with `command=/alldata/read` |
| Write commands | Same endpoint with `command=/{key}/write`, `params=value={val}` |
| Python class | `I2dSystem` in `src/iaqualink/systems/i2d/system.py` |

## System Status Lifecycle

Status is derived from the `alldata.opmode` field in the response.

### Status mapping

| Condition | `SystemStatus` |
|-----------|----------------|
| `opmode` present and `<= 3` | `CONNECTED` |
| `opmode` present and `> 3` | `SERVICE` |
| `opmode` absent, `updateprogress` not `"0"` / `"0/0"` | `FIRMWARE_UPDATE` |
| `opmode` absent, `updateprogress` is `"0"` or `"0/0"` | `UNKNOWN` |
| Device offline (see below) | `OFFLINE` |
| Network / HTTP error (non-401, non-429) | `DISCONNECTED` |
| HTTP 429 (throttled) | `UNKNOWN` |

### Device offline signals

The server signals device-offline in two ways, both treated identically:

1. **HTTP 200 with error body** — the API is reachable but the device is not:
   ```json
   {"status":"500","error":{"error_code":"error_internal_server_error","message":"Device offline.","details":"..."}}
   ```

2. **HTTP 500** — the API itself returns a 5xx with the same body structure.

In both cases, `system.status` is set to `SystemStatus.OFFLINE` and `refresh()` returns normally — no exception is raised to the caller.

## Device Model

All devices share a single data dict. Any `update()` call refreshes all device values atomically, since `motordata` is flattened into the top-level dict at parse time.

### Device breakdown

| Class | Key(s) | Type |
|---|---|---|
| `I2dPump` | `iqpump` | Pump on/off, presets, speed percentage |
| `I2dNumber` | `globalrpmmin`, `globalrpmmax`, `customspeedrpm`, `primingrpm`, `quickcleanrpm`, `freezeprotectrpm`, `countdownrpm`, `relayK1Rpm`*, `relayK2Rpm`*, `customspeedtimer`, `primingperiod`, `quickcleanperiod`, `freezeprotectperiod`, `countdownperiod`, `timeoutperiod`, `freezeprotectsetpointc` | Writable numeric setting |
| `I2dSwitch` | `freezeprotectenable` | Binary on/off setting |
| `I2dSensor` | `speed`, `power`, `temperature`, `horsepower`, `primingtimer`, `quickcleantimer`, `countdowntimer`, `timeouttimer`, `currentspan`, `wifistate`, `wifissid`, `fwversion`, `updateprogress`, `updateflag` | Read-only telemetry |
| `I2dBinarySensor` | `freezeprotectstatus` | Read-only binary flag |

*Only present on hardware with relay outputs.

### RPM bounds design

RPM numbers (except `globalrpmmin`/`globalrpmmax`) use `globalrpmmin`/`globalrpmmax` as **live bounds** from the shared data dict. This means changing the global bounds immediately constrains all other RPM numbers without a page refresh.

`globalrpmmin` uses a hardware minimum (`_rpmhwmin`) injected at parse time from `productid`:
- Non-SVRS products: 600 RPM
- SVRS products (0F/18): 1050 RPM

Speed percentage mapping: `set_speed_percentage(0–100)` normalises to the hardware RPM range, rounded to the nearest 25 RPM.

### Period/timer numbers

Period and timer settings are in **seconds** with explicit step values:

| Key | Range | Step |
|---|---|---|
| `quickcleanperiod` | 300–3600 | 300 |
| `primingperiod` | 30–600 | 30 |
| `countdownperiod` | 60–43200 | 60 |
| `timeoutperiod` | 60–43200 | 60 |
| `freezeprotectperiod` | 60–43200 | 60 |
| `customspeedtimer` | 60–43200 | 60 |

### Settable opmodes

| Opmode | Wire value | Settable? |
|---|---|---|
| SCHEDULE | `0` | Yes |
| CUSTOM | `1` | Yes |
| STOP | `2` | Yes |
| QUICK_CLEAN | `3` | No — pump enters automatically |
| TIMED_RUN | `4` | No — pump enters automatically |
| TIMEOUT | `5` | No — pump enters automatically |
| SERVICE_OFF | `6` | No — pump enters automatically |

## Design Decisions

### `updateprogress "0"` treated as no-update-in-progress

When `opmode` is absent and `updateprogress="0"`, the library sets `UNKNOWN`. The reference app treats `"0"` as distinct from `"0/0"` and considers the device reachable in that state. In practice this path is unreachable during normal operation (`opmode` is always present); `UNKNOWN` is the conservative choice for the ambiguous case.

### Schedule not implemented

`/schedule/read` and `/schedule/write` are fully defined in the reference protocol but not implemented in the library. Schedule state is readable via the `currentspan` sensor (`"-1"` = no active span).

### Local access not implemented

The reference protocol defines a local (same-LAN) access path at `http://192.168.0.1`. The library uses only the cloud path.

## Deltas vs Protocol Reference

| # | Observed reference | Current Python (`I2dSystem`) |
|---|---|---|
| 1 | `/schedule/read` and `/schedule/write` defined | Not implemented |
| 2 | `demandvisible` / `faultvisible` in alldata | Not exposed; values observed: `"0"` only |
| 3 | Firmware endpoints: `/latest_firmware_version`, OTA trigger | Not implemented |
| 4 | Local access at `http://192.168.0.1` | Not implemented; cloud-only |

## See Also

- [Protocol Reference: i2d](../reference/i2d.md) — wire-level spec
- [API Reference: i2d](../api/i2d.md) — class and method docs
