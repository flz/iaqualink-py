# i2d Protocol Reference

## Overview

`i2d` is the `device_type` value returned in the device list for Zodiac iQPump
variable-speed pool pumps. All cloud communication goes through
`https://r-api.iaqualink.net`. A second local path exists for direct (same-LAN)
access at `http://192.168.0.1` but is not used by this library.

Two control URL generations exist in the app:

| Generation | URL pattern |
|---|---|
| v1 (legacy) | `https://r-api.iaqualink.net/devices/{serial}/control.json` |
| v2 (current) | `https://r-api.iaqualink.net/v2/devices/{serial}/control.json` |

The library uses v2.

---

## Authentication

All v2 control requests require two headers:

| Header | Value |
|---|---|
| `Authorization` | `{IdToken}` — the Cognito JWT returned at login in `userPoolOAuth.IdToken` |
| `api_key` | `EOOEMOW4YR6QNB07` — the production API key |

`IdToken` is sent **bare** (no `Bearer` prefix) on these endpoints. This matches
the legacy iQ20 pattern, not the `Bearer`-prefixed variant used by some other
endpoints.

The request body also carries `user_id` and `authentication_token` (see
§Request Body below). The app passes both header auth and body auth
simultaneously.

---

## Endpoints

### POST /v2/devices/{serial}/control.json

Full URL: `https://r-api.iaqualink.net/v2/devices/{serial}/control.json`

Used for **all** i2d operations — both reads (`/alldata/read`) and all writes.
The operation is selected by the `command` field in the JSON body.

**Request headers:**

```
Authorization: {IdToken}
api_key: EOOEMOW4YR6QNB07
Content-Type: application/json
Accept: application/json
```

**Request body:**

```json
{
  "api_key":            "EOOEMOW4YR6QNB07",
  "authentication_token": "{authentication_token}",
  "user_id":            {user_id},
  "command":            "{command_path}",
  "params":             "{params_string}"
}
```

- `user_id` is an integer in the wire format.
- `params` is a plain string (e.g. `"value=1500"`), not a nested object.
- For read commands, `params` is an empty string `""`.

**Response headers:** `Content-Type: application/json`

**Error detection:** The server returns HTTP 200 even when the device is
unreachable. A failed response carries `"status": "500"` at the top level with
an `error.message` sub-key.

---

### GET /devices/{serial}/update_firmware  (firmware — not implemented)

Triggers an OTA firmware update. Not used by this library. Also available as
`/v2/devices/{serial}/update_firmware`.

### GET /devices/{serial}/latest_firmware_version  (firmware — not implemented)

Returns available firmware metadata. Response shape:

```json
{
  "latest_firmware_version": "...",
  "latest_AtlasVSP_firmware_version": "...",
  "min_AtlasVSP_firmware_version": "..."
}
```

---

## Commands

All commands are sent as the `command` field in the POST body to the v2 control
endpoint.

### /alldata/read

Fetches the full device state snapshot. `params` is `""`.

Response shape:

```json
{
  "alldata": {
    "opmode":               "0",
    "runstate":             "on",
    "fwversion":            "1.5.2",
    "RS485fwversion":       "1.0.0",
    "serialnumber":         "ABC123",
    "localtime":            "12:34",
    "timezone":             "America/Los_Angeles",
    "utctime":              "1700000000",
    "hotspottimer":         "5",
    "busstatus":            "0",
    "updateprogress":       "0",
    "updateflag":           "0",
    "rpmtarget":            "1500",
    "globalrpmmin":         "600",
    "globalrpmmax":         "3450",
    "customspeedrpm":       "1500",
    "customspeedtimer":     "60",
    "quickcleanrpm":        "3450",
    "quickcleanperiod":     "8",
    "quickcleantimer":      "0",
    "countdownrpm":         "1500",
    "countdownperiod":      "30",
    "countdowntimer":       "0",
    "timeoutperiod":        "10",
    "timeouttimer":         "0",
    "primingrpm":           "3450",
    "primingperiod":        "3",
    "primingtimer":         "0",
    "freezeprotectenable":  "1",
    "freezeprotectrpm":     "1000",
    "freezeprotectperiod":  "30",
    "freezeprotectsetpointc": "4",
    "freezeprotectstatus":  "0",
    "currentspan":          "-1",
    "demandvisible":        "0",
    "faultvisible":         "0",
    "relayK1Rpm":           "1500",
    "relayK2Rpm":           "1200",
    "motordata": {
      "speed":              "1500",
      "power":              "180",
      "temperature":        "110",
      "productid":          "1A",
      "horsepower":         "1.65",
      "horsepowercode":     "0A",
      "updateprogress":     "0"
    },
    "wifistatus": {
      "state":              "connected",
      "ssid":               "MyNetwork"
    }
  },
  "requestID": "1234"
}
```

All values are JSON strings, not numbers.

### /{key}/write

Writes a single setting. `params` is `"value={val}"` (e.g. `"value=1500"`).
The response wraps the written key in an object alongside `requestID`:

```json
{
  "{key}": {
    "operation": "write",
    "value":     "{val}"
  },
  "requestID": "1234"
}
```

Example — writing `opmode`:

```json
{
  "opmode": { "operation": "write", "value": "1" },
  "requestID": "1234"
}
```

### /schedule/read  (not implemented in this library)

Reads schedule configuration. Response wraps a `schedule` key with
`{ "operation": "read", "value": "..." }`.

### /schedule/write  (not implemented in this library)

Writes schedule configuration. Same body/response pattern as other write
commands.

### /wifiscan/read  (not implemented)

Scans for available WiFi networks.

### /wifijoin/write  (not implemented)

Joins a WiFi network.

### /utctime/write  (not implemented)

Sets the UTC timestamp on the device.

### /timezone/write  (not implemented)

Sets the device timezone region string.

### /timezoneinfo/write  (not implemented)

Sets extended timezone info on the device.

### /hotspottimer/write  (not implemented)

Sets the WiFi hotspot auto-off timer.

### /serialnumber/read  (not implemented)

Returns the device serial number.

---

## State Fields

All field values are JSON strings. The `motordata` sub-object is a nested
object inside `alldata` in the wire response. The library flattens
`motordata` fields into the top-level dict at parse time.

### Top-level alldata fields

| Field | Type | Notes |
|---|---|---|
| `opmode` | string | Current operating mode — see §Opmode Values |
| `runstate` | string | `"on"` or `"off"` — motor physically spinning |
| `fwversion` | string | Wi-Fi module firmware version (e.g. `"1.5.2"`) |
| `RS485fwversion` | string | RS-485 motor firmware version (e.g. `"1.0.0"`) |
| `serialnumber` | string | Device serial number |
| `localtime` | string | Device local time (`"HH:MM"`) |
| `timezone` | string | Timezone region name (e.g. `"America/Los_Angeles"`) |
| `utctime` | string | Unix timestamp as string |
| `hotspottimer` | string | WiFi hotspot auto-off timer (minutes) |
| `busstatus` | string | RS-485 bus status; `"2"` = error/fault |
| `updateprogress` | string | OTA progress; `"0"` or `"0/0"` = idle; other = updating |
| `updateflag` | string | OTA pending flag |
| `rpmtarget` | string | Target RPM currently commanded |
| `globalrpmmin` | string | User-configured minimum RPM (settable) |
| `globalrpmmax` | string | User-configured maximum RPM (settable) |
| `customspeedrpm` | string | Custom speed mode RPM setpoint |
| `customspeedtimer` | string | Custom speed duration (seconds) |
| `quickcleanrpm` | string | Quick clean RPM setpoint |
| `quickcleanperiod` | string | Quick clean duration (seconds) |
| `quickcleantimer` | string | Quick clean remaining time (seconds) |
| `countdownrpm` | string | Countdown/timed-run RPM setpoint |
| `countdownperiod` | string | Countdown duration (seconds) |
| `countdowntimer` | string | Countdown remaining time (seconds) |
| `timeoutperiod` | string | Timeout mode duration (seconds) |
| `timeouttimer` | string | Timeout remaining time (seconds) |
| `primingrpm` | string | Priming RPM setpoint |
| `primingperiod` | string | Priming duration (seconds) |
| `primingtimer` | string | Priming remaining time (seconds) |
| `freezeprotectenable` | string | `"1"` = enabled, `"0"` = disabled |
| `freezeprotectrpm` | string | Freeze protection RPM |
| `freezeprotectperiod` | string | Freeze protection run duration (seconds) |
| `freezeprotectsetpointc` | string | Freeze trigger temperature in °C |
| `freezeprotectstatus` | string | `"0"` = inactive, `"1"` = active |
| `currentspan` | string | Index of currently active schedule span; `"-1"` = none |
| `demandvisible` | string | UI visibility flag |
| `faultvisible` | string | UI visibility flag |
| `relayK1Rpm` | string | RPM setpoint for auxiliary relay K1 output |
| `relayK2Rpm` | string | RPM setpoint for auxiliary relay K2 output |

### motordata fields

Nested under `alldata.motordata` in the wire response. Flattened into the
top-level device data dict by the library.

| Field | Type | Notes |
|---|---|---|
| `speed` | string | Current motor speed (RPM) |
| `power` | string | Current motor power (Watts) |
| `temperature` | string | Motor winding temperature (°F) |
| `productid` | string | Hardware product variant code — see §Product IDs |
| `horsepower` | string | Rated horsepower (e.g. `"1.65"`) |
| `horsepowercode` | string | Horsepower code byte (hex string, e.g. `"0A"`) |
| `updateprogress` | string | Motor firmware OTA progress (mirrors top-level field) |

### wifistatus fields

Nested under `alldata.wifistatus` in the wire response. Not flattened into the
top-level dict; the library traverses the sub-object at read time via path-based
access and exposes the fields as `I2dSensor` devices ("WiFi State" / "WiFi SSID",
device keys `"wifistate"` / `"wifissid"`).

| Field | Type | Notes |
|---|---|---|
| `state` | string | WiFi connection state (e.g. `"connected"`) — exposed as device `"wifistate"` |
| `ssid` | string | Connected network SSID — exposed as device `"wifissid"` |

---

## Opmode Values

The `opmode` field controls and reports the pump's operating mode.

| Value | Name | Settable | Notes |
|---|---|---|---|
| `"0"` | SCHEDULE | yes | Running on schedule program |
| `"1"` | CUSTOM | yes | Custom speed mode (uses `customspeedrpm`) |
| `"2"` | STOP | yes | Pump stopped |
| `"3"` | QUICK\_CLEAN | no | Entered automatically; short high-speed run |
| `"4"` | TIMED\_RUN | no | Entered automatically; uses `countdownrpm`/`countdownperiod` |
| `"5"` | TIMEOUT | no | Entered automatically; service timeout |
| `"6"` | (undefined) | no | Not observed in reference |
| `"7"` | SERVICE\_OFF | no | Entered automatically; service lockout |

Modes `"0"`, `"1"`, `"2"` are the only values accepted by `/opmode/write`.
The app constants confirm: `"value=0"` = SCHEDULE, `"value=1"` = CUSTOM,
`"value=2"` = STOP.

The app treats `opmode` values `"4"`, `"5"`, and `"7"` as "service mode"
(read-only states). Value `"3"` (QUICK\_CLEAN) is distinct from service mode
in the app logic.

A pump is considered running when `runstate == "on"` AND `opmode != "2"`.

A pump is considered in priming mode when `primingtimer > 0` AND
`busstatus != "2"` AND not in service mode AND not in STOP mode.

---

## Product IDs

The `productid` field (from `motordata`) identifies the motor hardware variant.
It is a hex string (e.g. `"0F"`, `"18"`, `"1A"`).

| productid | Variant | Notes |
|---|---|---|
| `"0F"` | SVRS | Safety Vacuum Release System pump |
| `"18"` | SVRS | Safety Vacuum Release System pump |
| other | Non-SVRS | All other variants |

SVRS vs non-SVRS affects the hardware minimum RPM floor (see §RPM Constants).

---

## RPM Constants

| Constant | Value | Applies to |
|---|---|---|
| Hardware RPM minimum (non-SVRS) | 600 | All product IDs except `"0F"` and `"18"` |
| Hardware RPM minimum (SVRS) | 1050 | Product IDs `"0F"` and `"18"` |
| Hardware RPM maximum | 3450 | All variants |
| RPM step | 25 | All RPM settings must be multiples of 25 |

`globalrpmmin` and `globalrpmmax` are the user-configured software limits
(settable via `/globalrpmmin/write` and `/globalrpmmax/write`). They are
bounded by the hardware floor and ceiling above.

RPM settings other than `globalrpmmin`/`globalrpmmax` use the live values of
`globalrpmmin` and `globalrpmmax` as their effective bounds.

The freeze-protect setpoint (`freezeprotectsetpointc`) is in **°C**, range
3–7, step 1. The app displays in °F (37–45 °F, step 2) and converts before
writing.

---

## Write Command Reference

All write commands follow the same pattern. `params` is `"value={integer}"`.

| Command | Writable range | Step | Notes |
|---|---|---|---|
| `/opmode/write` | 0, 1, 2 | — | See §Opmode Values |
| `/globalrpmmin/write` | hardware\_min – globalrpmmax | 25 | RPM |
| `/globalrpmmax/write` | globalrpmmin – 3450 | 25 | RPM |
| `/customspeedrpm/write` | globalrpmmin – globalrpmmax | 25 | RPM |
| `/quickcleanrpm/write` | globalrpmmin – globalrpmmax | 25 | RPM |
| `/primingrpm/write` | globalrpmmin – globalrpmmax | 25 | RPM |
| `/freezeprotectrpm/write` | globalrpmmin – globalrpmmax | 25 | RPM |
| `/countdownrpm/write` | globalrpmmin – globalrpmmax | 25 | RPM |
| `/relayK1Rpm/write` | globalrpmmin – globalrpmmax | 25 | Aux relay K1 RPM; relay hardware floor: 600 (non-SVRS), 500 (SVRS) |
| `/relayK2Rpm/write` | globalrpmmin – globalrpmmax | 25 | Aux relay K2 RPM; relay hardware floor: 600 (non-SVRS), 500 (SVRS) |
| `/customspeedtimer/write` | 300 – 3600 | 300 | Seconds |
| `/primingperiod/write` | 0 – 300 | 60 | Seconds |
| `/quickcleanperiod/write` | 300 – 3600 | 300 | Seconds |
| `/freezeprotectperiod/write` | 0 – 28800 | 1800 | Seconds |
| `/countdownperiod/write` | 3600 – 86400 | 3600 | Seconds |
| `/timeoutperiod/write` | 3600 – 86400 | 3600 | Seconds |
| `/freezeprotectenable/write` | 0, 1 | — | 0=off, 1=on |
| `/freezeprotectsetpointc/write` | 3 – 7 | 1 | °C |
| `/schedule/write` | — | — | Not implemented |
| `/hotspottimer/write` | — | — | Not implemented |
| `/utctime/write` | — | — | Not implemented |
| `/timezone/write` | — | — | Not implemented |
| `/timezoneinfo/write` | — | — | Not implemented |
| `/wifijoin/write` | — | — | Not implemented |

---

## Error / Status Codes

| Condition | Wire indicator |
|---|---|
| Device unreachable (cloud) | HTTP 200 with `"status": "500"` in body |
| Bus fault / motor error | `busstatus == "2"` |
| OTA in progress | `updateprogress` not `"0"` and not `"0/0"` |
| No schedule active | `currentspan == "-1"` |

---

## Direct (local) Access

The device also exposes an HTTP server at `http://192.168.0.1` on the local
network with the same `/alldata/read` and `/{key}/write` commands. This path
uses GET with no body (read) or a query parameter form (write). The library
does not implement local access.
