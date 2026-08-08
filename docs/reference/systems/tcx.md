# tcx — Filtration & Spa Controller Protocol

**Python system name:** `"tcx"`
**Wire device type:** `"tcx"`
**Protocol family:** AWS IoT Device Shadow (real-time push via MQTT or WebSocket)
**Auth:** See [client.md](../client.md)

---

## Overview

TCX controllers communicate via the AWS IoT Device Shadow protocol on
`prod.zodiac-io.com`. Unlike the session-command model used by iAqua/iQ20,
TCX exposes all device state as a JSON shadow document. Reads retrieve the
full `reported` state; writes post a `desired` state delta that the device
reconciles asynchronously.

State is split across multiple shadow documents — a main shadow plus
per-subsystem sub-shadows — to stay within the AWS IoT 8 KB shadow size
limit. Real-time updates are delivered over MQTT subscriptions or a
WebSocket stream (transport is configurable server-side).

---

## Shadow Endpoints

### Base URL

```
https://prod.zodiac-io.com
```

### Main Shadow (read)

```
GET /devices/v2/{serial}/shadow?signature={sig}
Authorization: Bearer {idToken}
```

Returns the full device shadow (`TcxAllData` envelope).

### Sub-Shadows (read)

```
GET /devices/v1/{serial}_{suffix}/shadow
Authorization: Bearer {idToken}
```

| Suffix | Subsystem |
|--------|-----------|
| `_filt` | Filtration pump |
| `_ecm` | Variable-speed pump (ECM/VSP) |
| `_sched` | Schedules |
| `_pib0` | PIB board |
| `_fea` | Feature flags |
| `_zig` | ZigBee paired devices |
| `_scene` | Scene definitions |

### Shadow Write

```
POST /devices/v2/{serial}/shadow
Authorization: Bearer {idToken}
Content-Type: application/json

{ "state": { "desired": { ... } } }
```

Sub-shadow writes use the same pattern with the suffixed serial:

```
POST /devices/v2/{serial}_{suffix}/shadow
```

### Firmware Version Check

```
GET /...?currentFirmware={version}&signature={sig}&deviceType={type}
Authorization: Bearer {idToken}
```

Response:

| Field | Type | Description |
|---|---|---|
| `hasMinFirmware` | boolean | Whether device meets minimum firmware |

---

## MQTT Topics

When the MQTT transport is active, the client subscribes to shadow topics directly on the AWS IoT broker (`a1zi08qpbrtjyq-ats.iot.us-east-1.amazonaws.com` in production).

| Purpose | Topic |
|---------|-------|
| Trigger full shadow fetch | `$aws/things/{serial}/shadow/get` (publish empty payload) |
| Receive full shadow | `$aws/things/{serial}/shadow/get/accepted` |
| Receive incremental updates | `$aws/things/{serial}/shadow/update/accepted` |
| Write desired state | `$aws/things/{serial}/shadow/update` |
| OTA events | `events/iaqualink/{serial}/{event}` |

Sub-shadows use the same patterns with `{serial}_{suffix}` in place of `{serial}`.

### Subscription lifecycle

1. Subscribe to `$aws/things/{serial}/shadow/get/accepted`
2. Publish empty payload to `$aws/things/{serial}/shadow/get` to trigger fetch
3. On receipt, inspect `state.reported.equipment` to determine which sub-shadows exist
4. Subscribe to each sub-shadow's `/get/accepted` topic and trigger their fetches
5. Once all sub-shadows are received, unsubscribe from all `/get/accepted` topics
6. Subscribe to `$aws/things/{serial}/shadow/update/accepted` for live deltas
7. Route incoming deltas to the appropriate sub-shadow by inspecting payload keys

---

## WebSocket Protocol

When the WebSocket transport is active (server-side default), the client connects to:

```
wss://prod-socket.zodiac-io.com{path}
Authorization: {idToken}
```

| Parameter | Value |
|-----------|-------|
| Ping interval | 120 s |
| Timeout | 600 s |

### Subscribe frame

```json
{
  "service": "Authorization",
  "target": "<serial>",
  "namespace": "authorization",
  "version": 1,
  "action": "subscribe",
  "payload": { "userId": <int> }
}
```

### Unsubscribe frame

```json
{
  "service": "Authorization",
  "target": "<serial>",
  "namespace": "authorization",
  "version": 1,
  "action": "unsubscribe",
  "payload": { "userId": <int> }
}
```

### Command frame

```json
{
  "service": "StateController",
  "target": "<serial>",
  "namespace": "<namespace>",
  "version": 1,
  "action": "<action>",
  "payload": { ..., "clientToken": "<userId>|<random>|<random>" }
}
```

### Incoming data frame

```json
{
  "service": "Authorization|StateStreamer|DataStreamer|ErrorStreamer|EventStreamer",
  "target": "<serial>",
  "namespace": "<namespace>",
  "payload": { ... }
}
```

Confirmed from live wire capture: for `service: "Authorization"` (full-state push on subscribe), `payload` is **namespace-keyed**, not a single flat `state.reported` object:

```json
{
  "payload": {
    "main":  { "state": { "reported": { "...top-level main fields..." } }, "metadata": { ... }, "version": <int>, "timestamp": <int> },
    "filt":  { "state": { "reported": { "filt0": { ... } } }, "metadata": { ... }, "version": <int>, "timestamp": <int> },
    "ecm":   { "state": { "reported": { "ecm0": { ... } } }, "metadata": { ... }, "version": <int>, "timestamp": <int> },
    "pib0":  { "state": { "reported": { "water": { ... }, "air": { ... }, "solar": { ... }, "aux0": { ... }, "lvh1": { ... } } }, "metadata": { ... }, "version": <int>, "timestamp": <int> },
    "zig":   { "state": { "reported": { "zig": { "...radio status..." }, "auxz0": { "...device..." } } }, "metadata": { ... }, "version": <int>, "timestamp": <int> },
    "fea":   { "state": { "reported": { "fea": {}, "fcr0": { ... } } }, "metadata": { ... }, "version": <int>, "timestamp": <int> },
    "sched": { "state": { "reported": { "sh": { ... } } }, "metadata": { ... }, "version": <int>, "timestamp": <int> },
    "scene": { "state": { "reported": { "scene": { ... } } }, "metadata": { ... }, "version": <int>, "timestamp": <int> },
    "data":  [ { "...telemetry sample..." } ],
    "ota":   { "jobId": null, "status": null, "statusDetails": {} }
  }
}
```

Each namespace's `state.reported` merges to reproduce the same flat device keys the main REST shadow (`state.reported`) would carry for that namespace — no key collisions observed across namespaces. `data` (a telemetry-sample array) and `ota` are not `{state: {reported: ...}}`-shaped and carry no device state.

`StateStreamer`/`DataStreamer`/`EventStreamer` delta payload shape has not been directly observed — whether it's the same namespace-keyed shape (likely, by analogy) or a flat `state.reported` remains unconfirmed.

---

## BLE Direct-Connect Fallback

When WiFi is unavailable, the app can communicate with the TCX over BLE.

| Parameter | Value |
|-----------|-------|
| Device name prefix | `"iAqua_"` |
| Write characteristic | `"Tcx_Data_Updates"` |
| Payload format | Raw desired-state JSON (no `{"state":{"desired":}}` wrapper) |

---

## Namespaces

WebSocket commands are scoped to a namespace that identifies the target subsystem:

| Namespace | Wire value | Scope |
|-----------|-----------|-------|
| TCX | `"tcx"` | Main device state |
| Filtration | `"filtration"` | Filter pump |
| VSP | `"vsp"` | Variable speed pump |
| Feature Circuit | `"featureCircuit"` | Feature circuits |
| PIB | `"pib"` | PIB board |
| ZigBee | `"zigbee"` | ZigBee devices |
| Scene | `"scene"` | Scenes |
| Schedule | `"schedule"` | Schedules |
| SWC | `"swc"` | Salt water chlorinator |

---

## Command Reference

### Main (namespace: `tcx`)

| Action wire value | Description |
|---|---|
| `"setState"` | Generic state update |
| `"setAuxSetup"` | Configure auxiliary relay |
| `"setAuxState"` | Toggle auxiliary on/off |
| `"setAuxLight"` | Set auxiliary light color |
| `"setAuxResetColor"` | Reset auxiliary light to default color |
| `"setAuxCleanerStatus"` | Set cleaner relay status |
| `"setWaterTempSetpoint"` | Set water temperature target |
| `"setSolarTempSetpoint"` | Set solar temperature target |
| `"setHeatEnabled"` | Enable/disable heater |
| `"setSolarHeatState"` | Enable/disable solar heater |
| `"setLvhAppType"` | Set LVH (light/valve/heater) application type |
| `"setSiteInfo"` | Update site location/timezone |
| `"setIsFCFreezeProtect"` | Enable/disable freeze control solar protection |
| `"setIsAux0FreezeProtect"` | Enable/disable aux 0 freeze protection |
| `"setFreezeSetPoint"` | Set freeze protection temperature threshold |
| `"initiateOTA"` | Start firmware update |

### Filtration (namespace: `filtration`)

| Action wire value | Description |
|---|---|
| `"setFilterPumpState"` | Toggle filter pump on/off |

### VSP (namespace: `vsp`)

| Action wire value | Description |
|---|---|
| `"setPrimingSpeed"` | Set priming speed (RPM) |
| `"setPrimingSpeedDuration"` | Set priming duration |
| `"setSpeedsList"` | Write full speed preset list |
| `"setMinMasterSpeed"` | Set minimum master speed |
| `"setMaxMasterSpeed"` | Set maximum master speed |
| `"setQuickCleanSpeed"` | Set quick-clean speed |
| `"setQuickCleanDuration"` | Set quick-clean duration |
| `"setFreezeProtectSpeed"` | Set freeze-protection speed |

### Feature Circuit (namespace: `featureCircuit`)

| Action wire value | Description |
|---|---|
| `"setFeatureCircuitSetup"` | Configure feature circuit |
| `"setFeatureCircuitState"` | Toggle feature circuit on/off |
| `"setFeatureTap"` | Trigger feature tap action |

### SWC (namespace: `swc`)

| Action wire value | Description |
|---|---|
| `"setBoostMode"` | Enable/disable SWC boost |
| `"setSwcDictionary"` | Set SWC configuration (mode, output %) |

### Schedule (namespace: `schedule`)

| Action wire value | Description |
|---|---|
| `"saveModifiedSchedule"` | Update an existing schedule |
| `"addSchedule"` | Create a new schedule |
| `"removeSchedule"` | Delete a schedule |
| `"setMultidayMode"` | Enable/disable multi-day scheduling |

### ZigBee (namespace: `zigbee`)

| Action wire value | Description |
|---|---|
| `"setZigbeeFriendlyName"` | Rename a ZigBee device |
| `"setZigbeeState"` | Toggle ZigBee device on/off |
| `"setZigbeeEquipmentType"` | Set ZigBee device equipment type |
| `"setZigBeeFunctionType"` | Set ZigBee device function type |
| `"setZigBeeCurrentColor"` | Set ZigBee light current color |
| `"setZigBeeResetColor"` | Reset ZigBee light color |
| `"setZigBeeAuxDictionary"` | Set ZigBee aux configuration |
| `"setZigbeeScanDuration"` | Set ZigBee scan discovery duration |

Confirmed `setZigbeeState` write shape (targets the `_zig` sub-shadow, keyed by the `auxz[N]` device, not by radio address):

```json
{ "state": { "desired": { "auxz0": { "st": 1 } } } }
```

Over MQTT this is a `POST`/publish to the `_zig` sub-shadow's update path (`$aws/things/{serial}_zig/shadow/update`); over WebSocket, namespace `"zigbee"`, action `"setZigbeeState"`, `payload: {"auxz0": {"st": 1}, "clientToken": ...}`.

---

## Shadow Response Envelope

All shadow GET responses share this envelope:

| Field | Type | Description |
|---|---|---|
| `state` | object | Contains `reported` (and optionally `desired`) |
| `metadata` | object | Per-field timestamps |
| `timestamp` | long | Unix timestamp of this response |
| `version` | long | Shadow version (increments on each update) |

---

## Reported State

The `state.reported` object contains 42 top-level fields representing the full device state.

### Identity & System

| JSON key | Type | Description |
|---|---|---|
| `sn` | string | Serial number |
| `model` | string | Device model identifier |
| `deviceType` | string | Always `"tcx"` |
| `firmwareVersion` | string | Current firmware version |
| `systemType` | long | System type code |
| `systemMode` | long | Service mode: values `3` or `4` = service mode (remote control blocked) |
| `tempSetting` | long | Temperature unit: `0` = °C, `1` = °F |

### Temperature Sensors

| JSON key | Type | Description |
|---|---|---|
| `air` | object | Air temperature sensor (see Air object) |
| `airTemp` | long | Air temperature raw value |
| `airSnsr` | string | Air sensor status |
| `water` | object | Water temperature (see Water object) |
| `freezeSP` | long | Freeze protection set point |
| `lowAirSP` | long | Low air temperature threshold |

Confirmed from live wire capture: `waterTempSet`, `water.value`, `solar.value`, `freezeSP`, and `lowAirSP` are all tenths of the active display unit (per `tempSetting`), not whole degrees — e.g. raw `283` is `28.3°C`, not `283°C`. `freezeSP=33`/`lowAirSP=128` only make sense as `3.3`/`12.8` (freeze protection and a low-air cutoff near freezing/mild); `airTemp` (whole-degree, unscaled per the original decompiled-source field table) has not been confirmed live — no example with real hardware data has been captured for it, since the field itself hasn't been observed on real hardware at all (see `docs/implementation/systems/tcx.md` Deltas #9/#10).

### Pool / Valve

| JSON key | Type | Description |
|---|---|---|
| `pool` | object | Pool pump state (see Pool object) |
| `valveMode` | long | Valve position (pool/spa/spillover) |

### Equipment & Subsystems

| JSON key | Type | Description |
|---|---|---|
| `equipment` | object | Equipment configuration; indicates which sub-shadows exist |
| `filt0` | object | Filtration pump (see Filt0 object) |
| `ecm0` | object | Variable-speed pump (see Ecm0 object) |
| `aux0` | object | Auxiliary relay (see Aux0 object) |
| `auxz0` | object | Auxiliary zone config |
| `jva1` | object | JVA valve actuator 1 |
| `jva2` | object | JVA valve actuator 2 |
| `lvh1` | object | Light/valve/heater 1 (heater tile state) |
| `pib0` | object | PIB board state |

### Heating

| JSON key | Type | Description |
|---|---|---|
| `TspBdy0` | object | Temperature set-point body 0 (see TspBdy0 object) |
| `solar` | object | Solar heater (see Solar object) |
| `fcSolar` | object | Solar freeze control |
| `fcr0` | object | Freeze control relay |

### Chemistry

| JSON key | Type | Description |
|---|---|---|
| `swc0` | object | Salt water chlorinator (see Swc0 object) |

### Features & Schedules

| JSON key | Type | Description |
|---|---|---|
| `fea` | object | Feature flags |
| `sh` | object | Schedule hub |

### Site

| JSON key | Type | Description |
|---|---|---|
| `site` | object | Location: address, city, country, latitude, longitude, postalCode, state, name |

### Connectivity

| JSON key | Type | Description |
|---|---|---|
| `aws` | object | AWS IoT connection — `status` (`"connected"` / `"disconnected"`), `timestamp` |
| `Bluetooth` | object | BLE connection info (note: capitalized key) |
| `connectionRSSI` | string | WiFi signal strength |
| `connectionType` | string | Connection type identifier |
| `zig` | object | ZigBee data |
| `hubAir` | object | Hub air sensor |
| `hubStatus` | long | Hub connection status |
| `hubTemp` | long | Hub temperature |

### Other

| JSON key | Type | Description |
|---|---|---|
| `spare` | object | Spare config |
| `reset` | object | Reset state |

---

## Sub-Object Schemas

### `pool`

| JSON key | Type | Description |
|---|---|---|
| `st` | integer | Pump state: `0` = off, `1` = on |
| `en` | long | Enabled |
| `cp` | boolean | Cool pool flag |
| `fp` | boolean | Freeze protect active |
| `zn` | array\<long\> | Zone assignment list |
| `ap` | string | Application type |
| `et` | string | Equipment type |
| `fr` | string | Friendly name |

### `water`

| JSON key | Type | Description |
|---|---|---|
| `value` | long | Current water temperature |
| `us` | long | Sensor status — see Water Status enum |
| `fr` | string | Friendly name |
| `en` | long | Enabled |
| `cp` | boolean | Cool pool flag |
| `zn` | array\<long\> | Zone assignment |

### `filt0` (Filtration Pump)

Corrected from live wire capture: the field table below reflects real hardware. An earlier version of this doc (decompiled-source-derived) listed abbreviated keys `sp`/`mn`/`mx`/`sl`/`ax` here — none of those appear on real hardware; the actual keys are the full names below, matching `ecm0`'s naming convention almost exactly (see `ecm0` table below).

| JSON key | Type | Description |
|---|---|---|
| `st` | long | Run status |
| `en` | long | Enabled |
| `manSpd` | long | Manual override speed (RPM) — confirmed **distinct** from `ecm0.manSpd` on real hardware, not a duplicate |
| `minSpd` | long | Minimum allowed speed (RPM) — matches `ecm0.minSpd` on real hardware |
| `maxSpd` | long | Maximum allowed speed (RPM) — matches `ecm0.maxSpd` on real hardware |
| `spdList` | array | Named speed preset list (see SpdList below) — matches `ecm0.spdList` on real hardware |
| `asAux` | string | Associated aux (observed empty string when unset) |
| `cp` | boolean | Cool pool |
| `app` | string | Application type |
| `et` | string | Equipment type |
| `fr` | string | Friendly name |
| `zn` | array\<long\> | Zone assignment |

### `ecm0` (Variable Speed Pump)

| JSON key | Type | Description |
|---|---|---|
| `cmdSpd` | long | Commanded speed (RPM) |
| `reqSpd` | long | Requested speed |
| `manSpd` | long | Manual override speed |
| `minSpd` | long | Minimum allowed speed |
| `maxSpd` | long | Maximum allowed speed |
| `frzSpd` | long | Freeze protection speed |
| `prmSpd` | long | Priming speed |
| `prmDur` | long | Priming duration (seconds) |
| `qcSpd` | long | Quick clean speed |
| `qcDur` | long | Quick clean duration (seconds) |
| `spdList` | array | Named speed preset list (see SpdList) |
| `st` | long | Current status |
| `en` | long | Enabled |
| `model` | string | Pump model identifier |
| `servTm` | long | Service timer |
| `cp` | boolean | Cool pool |
| `et` | string | Equipment type |
| `fr` | string | Friendly name |
| `app` | string | Application type |
| `asAux` | string | Associated aux |
| `zn` | array\<long\> | Zone assignment |

### `spdList` Element (Speed Preset)

Elements of `ecm0.spdList`:

| JSON key | Type | Description |
|---|---|---|
| `speed` | long | Preset speed (RPM) |
| `name` | string | Preset name |
| `app` | string | Application type |
| `ar` | long | Auto-run flag |

### `TspBdy0` (Heater / Temperature Set-Point Body 0)

Note: JSON key uses uppercase `T`.

| JSON key | Type | Description |
|---|---|---|
| `waterTempSet` | long | Water temperature set point |
| `solarTempSet` | integer | Solar temperature set point |
| `heatEnabled` | boolean | Heater enabled |
| `heatPriority` | long | Heat priority mode |
| `heatAvailable` | long | Available heat sources bitmask |
| `gasEn` | boolean | Gas heater available |
| `solarEn` | boolean | Solar heater available |
| `status` | long | Heater operating status |
| `value` | long | Current heater value |
| `name` | string | Body name |
| `type` | long | Body type |
| `zone` | long | Zone assignment |

### `lvh1` (Heater Tile State)

Drives the heater home-screen tile:

| `en` value | Meaning |
|---|---|
| `0` | Off |
| `1`–`5` | Standby |
| `6` | Heating (active) |
| `≥ 7` | Off |

| JSON key | Type | Description |
|---|---|---|
| `en` | long | Heater state — see table above |
| `app` | string | `"HEAT"` (heater configured) or `"OFF"` |
| `st` | long | Current status |
| `cd` | long | Countdown timer |
| `cl` | boolean | Cool pool |
| `cp` | boolean | Cool pool flag |
| `et` | string | Equipment type |
| `fr` | string | Friendly name |
| `model` | string | Heater model identifier |
| `zn` | array\<long\> | Zone assignment |

### `solar`

| JSON key | Type | Description |
|---|---|---|
| `value` | long | Solar sensor temperature reading |
| `us` | long | Sensor status — see Solar Status enum |
| `en` | long | Enabled |
| `ty` | long | Solar type |
| `de` | boolean | Device enabled |
| `se` | boolean | Sensor enabled |
| `ac` | long | Active/action state |
| `du` | long | Duration |
| `dt` | long | Delta temperature |
| `to` | string | Timeout/target |
| `app` | string | Application type |
| `asAux` | string | Associated aux |
| `cp` | boolean | Cool pool |
| `et` | string | Equipment type |
| `fr` | string | Friendly name |
| `zn` | array\<long\> | Zone assignment |

### `swc0` (Salt Water Chlorinator)

Note: JSON key includes trailing `0`.

| JSON key | Type | Description |
|---|---|---|
| `outputPcnt` | integer | Current output percentage |
| `stdPoolPcnt` | integer | Standard mode pool output % |
| `lowPoolPcnt` | integer | Low mode pool output % |
| `boost` | integer | Boost mode active flag |
| `boostDur` | integer | Boost duration setting |
| `boostTime` | integer | Boost timer remaining |
| `swcMode` | integer | Chlorination mode — see SwcMode enum |
| `salinity` | integer | Salt level reading |
| `en` | integer | Enabled |
| `st` | integer | Cell status |
| `productName` | string | SWC product name |
| `app` | string | Application type |
| `cp` | boolean | Cool pool |
| `et` | string | Equipment type |
| `fr` | string | Friendly name |
| `zn` | array\<integer\> | Zone assignment |

### `aux0` (Auxiliary Relay)

| JSON key | Type | Description |
|---|---|---|
| `st` | integer | State: `0` = off, `1` = on |
| `en` | integer | Enabled (`2` = delay mode) |
| `app` | string | Application type — see AuxApp enum |
| `et` | string | Light type — see LightType enum |
| `fr` | string | Friendly name |
| `fp` | boolean | Freeze protect |
| `currClr` | integer | Current color index |
| `cmdClr` | integer | Commanded color index |
| `lockClr` | integer | Locked color index |
| `rstClr` | integer | Reset/default color index |
| `svdClr` | integer | Saved color index |
| `statClr` | integer | Color status — see ColorStatus enum |
| `dl` | integer | Dimmer level |
| `ty` | integer | Type code |
| `em` | integer | (reserved) |
| `sy` | integer | (reserved) |
| `rs` | string | Reset string |
| `cp` | boolean | Cool pool |
| `zn` | array\<integer\> | Zone assignment |

### `pib0` (PIB Board)

| JSON key | Type | Description |
|---|---|---|
| `sn` | string | PIB serial number |
| `vr` | string | PIB firmware version |
| `pibConfig` | long | PIB configuration flags |
| `app` | object | App metadata |

### `jva1` / `jva2` (JVA Valve Actuators)

Both `jva1` and `jva2` share the same schema:

| JSON key | Type | Description |
|---|---|---|
| `st` | long | State: `0` = off, `1` = on |
| `en` | long | Enabled |
| `pc` | long | Position counter |
| `app` | string | Application type |
| `cp` | boolean | Cool pool |
| `et` | string | Equipment type |
| `fr` | string | Friendly name |
| `rs` | string | Reset string |
| `zn` | array\<long\> | Zone assignment |

### `fcr0` (Freeze Control Relay) / `fcSolar` (Solar Freeze Control)

Both share the same schema:

| JSON key | Type | Description |
|---|---|---|
| `st` | integer | State: `0` = off, `1` = on |
| `en` | integer | Enabled |
| `sp` | integer | Set point |
| `ar` | integer | Auto-run flag |
| `app` | string | Application type |
| `asAux` | string | Associated aux |
| `cp` | boolean | Cool pool |
| `et` | string | Equipment type |
| `fp` | boolean | Freeze protect active |
| `fr` | string | Friendly name |
| `jv` | string | JVA association |
| `rs` | string | Reset string |
| `zn` | array\<integer\> | Zone assignment |

### `auxz0` (Auxiliary Zone Config)

| JSON key | Type | Description |
|---|---|---|
| `st` | long | State |
| `en` | long | Enabled |
| `ty` | long | Type code |
| `app` | string | Application type |
| `cm` | long | Config mode |
| `cp` | boolean | Cool pool |
| `currClr` | integer | Current color index |
| `cmdClr` | integer | Commanded color index |
| `dl` | long | Dimmer level |
| `ei` | string | Equipment identifier |
| `em` | long | (reserved) |
| `et` | string | Equipment type |
| `fp` | boolean | Freeze protect |
| `fr` | string | Friendly name |
| `lockClr` | integer | Locked color index |
| `man` | string | Manual mode |
| `model` | string | Model identifier |
| `ni` | string | Network identifier |
| `present` | long | Present flag |
| `rstClr` | integer | Reset/default color |
| `statClr` | integer | Color status |
| `svdClr` | integer | Saved color |
| `sy` | long | (reserved) |
| `ty` | long | Type code |
| `zn` | array\<long\> | Zone assignment |

### `zig` (ZigBee Hub Info — `_zig` sub-shadow)

Confirmed: `zig`/`auxz[N]` are **not** populated in the main shadow. The main shadow's `equipment.zig` is only a presence flag that gates whether the client subscribes to the `_zig` sub-shadow (see "MQTT Topics" above — same get/get-accepted/update-accepted lifecycle as every other sub-shadow). The actual reported state lives exclusively in the `_zig` sub-shadow document (`{serial}_zig`), and is what shows up merged into the unified WS Authorization payload's `"zig"` namespace (see "Incoming data frame" above) — the WS gateway delivers it unconditionally alongside every other namespace, with no client-side equivalent of the MQTT subscribe/trigger-fetch dance required.

The `zig` key itself holds hub-level ZigBee radio info (not per-device — individual paired devices are the `auxz[N]` keys documented above):

| JSON key | Type | Description |
|---|---|---|
| `st` | long | Hub state |
| `op` | long | Operating mode |
| `ty` | string | Hub type |
| `euid` | string | Extended unique identifier |
| `ai` | string | Additional info |
| `bt` | string | Bluetooth info |
| `fw` | string | Firmware version |

### `hubAir` (Hub Air Sensor)

| JSON key | Type | Description |
|---|---|---|
| `value` | integer | Air temperature reading |
| `us` | integer | Sensor status |

### `sl` Element (Schedule Slot)

Elements of `filt0.sl`:

| JSON key | Type | Description |
|---|---|---|
| `sn` | string | Slot name |
| `ss` | long | Schedule state/type |
| `ap` | string | Application type |
| `ar` | long | Auto-run flag |

### `equipment`

Indicates which sub-shadow documents exist for this device:

| JSON key | Type | Description |
|---|---|---|
| `ecm` | object | ECM equipment present |
| `fea` | object | Features present |
| `filt` | object | Filtration present |
| `pib0` | object | PIB board present |
| `scene` | object | Scene definitions present |
| `sched` | object | Schedules present |
| `swc` | object | SWC present |
| `zig` | object | ZigBee present |

### `site`

| JSON key | Type | Description |
|---|---|---|
| `latitude` | string | GPS latitude |
| `longitude` | string | GPS longitude |
| `timeZone` | string | Timezone ID |
| `time_zone` | string | Timezone ID (alternate key) |
| `localUTC` | long | Local UTC offset |
| `daylightSaving` | boolean | Daylight saving enabled |
| `daylight_savings` | integer | Daylight saving offset value |
| `daylightSavingActive` | boolean | Daylight saving currently active |

### `aws`

| JSON key | Type | Description |
|---|---|---|
| `status` | string | `"connected"` or `"disconnected"` |
| `timestamp` | long | Last connection state change timestamp |
| `session_id` | string | AWS IoT session ID |
| `versionNumber` | long | Shadow version number |

---

## Enum Wire Values

### SwcMode

| Wire value | Meaning |
|---|---|
| `0` | Standard |
| `1` | Low |
| `2` | Boost |

### AuxApp

Application type for `aux0.app`:

| Wire value | Meaning |
|---|---|
| `"ON"` | Generic on/off |
| `"UNUSED"` | Not configured |
| `"OTH"` | Other |
| `"WF"` | Waterfall |
| `"POOL_LT"` | Pool light |
| `"CLNR"` | Cleaner |

### LightType

Light equipment type for `aux0.et`:

| Wire value | Meaning |
|---|---|
| `"JL"` | Jandy WaterColors |
| `"IB"` | Pentair IntelliBrite |
| `"PSS"` | Pentair SAM/SAL |
| `"HU"` | Hayward Universal ColorLogic |
| `"WL"` | White Light (non-color) |

### ColorStatus

Color source for `aux0.statClr`:

| Wire value | Meaning |
|---|---|
| `4` or `5` | Use `currClr` (current color active) |
| `6` | Use `lockClr` (color locked) |

### Water Status

Sensor status for `water.us`:

| Wire value | Meaning |
|---|---|
| `1` | Valid temperature reading |
| `2` | Pump off — temperature unavailable |
| `3` | Loading/in-progress |
| `4` | Sensor unavailable |
| `5` | Sensor unavailable |

### Solar Status

Sensor status for `solar.us`:

| Wire value | Meaning |
|---|---|
| `1` | Present and visible (valid reading) |
| `4` | Sensor "Open" (fault) |
| `5` | Sensor "Short" (fault) |

### DeviceStatus (derived)

Combined status derived from `aws.status` and `systemMode`:

| Condition | Status | UI |
|---|---|---|
| `systemMode` = `3` or `4` | Service | Service mode dialog; remote control disabled |
| `aws.status` = `"connected"` | Connected | Online |
| `aws.status` = `"disconnected"` | Disconnected | Offline dialog |
| Shadow fetch in progress | In Progress | Loading |
| OTA in progress | Firmware Update | Update UI |

### OtaStatus

| Wire value | Meaning |
|---|---|
| `"IN_PROGRESS"` | Update in progress |
| `"INPROGRESS"` | Update in progress (alternate) |
| `"SUCCEEDED"` | Update completed successfully |
| `"SUCCESS"` | Update completed successfully (alternate) |
| `"UP_TO_DATE"` | Firmware already current |
| `"1POINTOF2"` | Stage 1 of 2-stage update |
| `"ERROR"` | Update failed |

---

## Error Handling

| Condition | Detection | Action |
|---|---|---|
| Device in service mode | `systemMode` = `3` or `4` | Block remote commands; show service dialog |
| Device offline | `aws.status` = `"disconnected"` | Show offline state; stop issuing commands |
| HTTP 401 | Response code | Trigger token refresh, retry once |
| Network error | Connection failure | Mark as disconnected |
| MQTT subscribe timeout | No response within timeout | Mark as unknown |

---

## Wire Format Notes

| # | Note |
|---|---|
| 1 | `TspBdy0` JSON key uses uppercase `T` — case-sensitive |
| 2 | `Bluetooth` JSON key uses uppercase `B` — case-sensitive |
| 3 | `swc0` key includes trailing `0` — not just `swc` |
| 4 | Main shadow GET uses `/devices/v2/`; sub-shadow GETs use `/devices/v1/` |
| 5 | HMAC signature required on main shadow GET requests (`?signature={sig}`); sub-shadow GETs and writes do not require it |
| 6 | WebSocket is the default transport; MQTT is enabled by server-side flag |
| 7 | BLE payloads omit the `{"state":{"desired":}}` wrapper — only the inner object is sent |
| 8 | `water.us` overloads sensor status with pump-off detection — not a pure temperature field |
| 9 | `systemMode` JSON key maps to service mode semantics (not to be confused with pool/spa mode) |
| 10 | WebSocket connection path is `/devices` (full URL: `wss://prod-socket.zodiac-io.com/devices`) |
| 11 | Reference app writes sub-shadows to `/devices/v1/{serial}_{suffix}/shadow` with a full state body; AWS shadow desired-state pattern (`/devices/v2/`) may also work server-side |
| 12 | `spdList` entries use field `speed` for the RPM value (not `spd`) |
| 13 | `site` in the shadow contains timezone and location fields; address/city/country fields are not part of the shadow document (they may appear on the `/devices/v2/{serial}/site` endpoint) |
| 14 | `aws.session_id` wire key uses underscore (`session_id`), not camelCase |

---

## Not Observed / Needs Verification

| # | Item |
|---|---|
| 1 | `valveMode` numeric values — exact mapping to pool/spa/spillover positions not confirmed from wire traffic |
| 2 | `systemType` enum values — code-level meaning not confirmed |
| 3 | `heatPriority` and `heatAvailable` value ranges — not confirmed |
| 4 | `equipment` sub-object field values — presence indicators beyond key presence not characterized |
| 5 | Feature-circuit element key — live capture shows `fcr[N]` (e.g. `fcr0`), not `feaCircuit[N]`; full field schema for an *enabled* circuit not yet observed (the one captured was disabled/`"app": "UNUSED"`) |
| 6 | ~~ZigBee device location~~ — **confirmed**: attached devices are separate top-level `auxz[N]` keys (e.g. `auxz0`) inside the `_zig` sub-shadow, analogous to `aux[N]`; `zig` itself is the radio's own status object (`st`/`op`/`euid`/`fw`/`ty`/`bt`/`ai`), not a dict of devices keyed by address. Write payload also confirmed: `{"state":{"desired":{"auxz0":{"st":1}}}}` (see "ZigBee" command reference above) |
| 7 | `ecm` sub-shadow URL (`tcx_ecm_shadow`) absent from production config — may not be fetched by reference app in production |
| 8 | ~~WS Authorization-ack payload body shape~~ — **confirmed** from live wire capture: namespace-keyed (see "Incoming data frame" above), not a flat `state.reported`. StateStreamer/DataStreamer/EventStreamer delta payload body shape remains unconfirmed — no delta frame observed live |
| 9 | Whether namespace-scoped *delta* pushes (`filtration`, `featureCircuit`, `zigbee`, etc. via StateStreamer/DataStreamer/EventStreamer) use the same namespace-keyed shape confirmed for the Authorization full-state push, or something else — not confirmed |
| 10 | Air sensor field — live capture shows no top-level `airTemp`/`airSnsr`; the air reading arrives as a full `air: {..., value, us}` object under the `pib0` namespace (same shape as `water`/`solar`), separate from a `hubAir`/`airSnsr` pair present at the main-namespace level |
| 11 | Per-action WS command payload field shapes (`StateController` frames) — only the envelope is documented in this spec; field-level bodies for each action (e.g. `setWaterTempSetpoint`, `setFilterPumpState`) have no confirmed example |

---

## See Also

- [Implementation Notes: TCX](../../implementation/systems/tcx.md) — status lifecycle, design decisions, accepted divergences from this spec (not yet written)
