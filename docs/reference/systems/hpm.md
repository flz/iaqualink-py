# hpm — Standalone Heat Pump Protocol

**Python system name:** `"hpm"`
**Protocol family:** AWS IoT shadow (REST polling, same mechanism as `exo`)
**Auth:** See [client.md](../client.md)

---

## Overview

A standalone Jandy/Fluidra heat-pump-only WiFi module — not attached to a full iQ20
(`iaqua`) pool controller. This is a different device from the `HPM` sub-device that
can be paired with an `iaqua` system (that one shares the parent controller's session
and reports through `iaqua`'s own shadow; this one has its own account-level device
entry with `device_type: "hpm"` and its own independent shadow).

### Confidence

Every field below was observed on the wire, but not every documented *value* was
reproduced. Values marked **unverified** were never observed on the one unit available
and should be treated as best-effort until someone can confirm them; everything else
was reproduced by driving the unit and comparing against the manufacturer app.

Only one unit was available, so single-unit assumptions — the `hp_0` index, Celsius
readings, the absence of set-point bounds — may not generalise.

---

## Shadow Endpoints (REST)

Same host and path shape as `exo`:

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

Same envelope as `exo`:

```json
{
  "state": {
    "reported": { ... },
    "desired":  { ... }
  }
}
```

The Python implementation reads only `state.reported`.

**Write propagation delay:** a `POST` is accepted immediately (HTTP 200, echoed back
under `state.desired`), but the unit can take upwards of 15 seconds to apply the change
and report it back under `state.reported`. A refresh issued straight after a write will
usually still read the old value.

### `state.reported` field reference

| Field | Type | Description |
|---|---|---|
| `aws.status` | string | Cloud connectivity. Matches the app's own online/offline indication. |
| `aws.timestamp` | integer | Time of the last report from the unit (ms). Stops advancing while the unit is disconnected — the whole `reported` block is then a cached last-known state, not a live read. |
| `ty` | string | Auxiliary dry-contact configuration, despite the name: `"UNK"` when no contact is configured, `"FP"` when one is. Gates whether the app lets `hp` be changed (see `hp`). `"FP"` **unverified** — the available unit has no contact wired. |
| `vr` | string | Top-level firmware version string. |
| `hmi` / `main` | object | OTA firmware metadata (URL, version, progress). Not modeled as entities. |
| `debug` | object | Diagnostic counters (RSSI, MQTT connection/reconnect counts, last error code, etc). Not modeled as entities. |

#### `equipment.hp_0` — the heat pump unit itself

| Field | Type | Description |
|---|---|---|
| `state` | integer (0/1) | Whether the unit is switched on. Echoes the last on/off command. |
| `status` | integer (0-3) | Operating state: `0` off, `1` standby, `2` heating, `3` cooling. |
| `reason` | integer (0-8) | Why the unit is in that state. `0` nothing to report, `1` no water flow, `3` within the temperature buffer ("Temp Buffer" in the app), `6` starting or stopping a compressor cycle — `6` accompanies any transition, so it is not purely an idle reason. `2` (ambient out of range), `4` (cool mode off), `5` (defrosting), `7` (remote contact open) and `8` (compressor protection delay) are **unverified**. |
| `tsp` | number | Target set point. No unit field exists; observed values were Celsius. |
| `fan` | integer (0/1/2) | Fan state. `0` while idle, nonzero whenever `status` is heating or cooling. `2` was seen only alongside `reason: 6`, and `1` during settled operation, suggesting a ramp-up speed, but the distinction is **unverified**. |
| `wf` | integer (0/1) | Whether the unit detects water flow. Tracks the circulation pump. |
| `st` | integer (0-2) | Performance mode: `0` boost, `1` silent, `2` smart. `2` is **unverified**; the app only offers it on some models. |
| `cl` | integer (0/1) | Whether the unit may cool. "Allow Cool Mode" in the app. Writing `1` puts a unit above its set point into cooling. |
| `hp` | integer (0/1) | Whether the unit may run off a dry-contact closure (e.g. from the filtration pump's run relay) instead of its own flow sensing. "Heating Priority" in the app, which locks the control unless `ty` is `"FP"`. Read constant `1` on a unit whose app showed it locked off, so the app's displayed state does not track this field while locked. **Unverified and deliberately not implemented** — see below. |
| `tmp` | integer | Meaning unknown; read constant `1`. **Unverified.** |
| `led` | integer | Meaning unknown, possibly a status LED; read constant `1`. **Unverified.** |
| `sn` | string | Heat pump serial, distinct from the account-level serial in the URL. |
| `vr` | string | Sub-device firmware version. |
| `compressorSpeed` (`cmprSpd`) | integer | Never populated on the available unit. |
| `errorCode` / `errorTime` | string | Never populated on the available unit; presumably set during a fault. |

**`sns_1` / `sns_2` — temperature probes** (nested inside `hp_0`):

| Field | Type | Description |
|---|---|---|
| `type` | string | `"water"` for `sns_1`, `"air"` for `sns_2`. |
| `state` | string | Whether the probe itself is wired up, independent of `aws.status`. Only `"connected"` was observed. |
| `value` | number | Temperature reading, matching the app's for the same probe. |

---

## Write Operations

All writes use the desired-state POST (see Endpoints above), scoped under
`equipment.hp_0`. Only include the field being changed.

### Set power state

```json
{
  "state": {
    "desired": {
      "equipment": {
        "hp_0": {
          "state": 1
        }
      }
    }
  }
}
```

### Set target set point

```json
{
  "state": {
    "desired": {
      "equipment": {
        "hp_0": {
          "tsp": 30
        }
      }
    }
  }
}
```

### Set performance mode or cooling

Same shape, targeting `st` or `cl` respectively.

`hp` accepts the same shape but is deliberately not implemented: exercising it needs a
dry contact wired to the unit, which no available unit had, and the app refuses to
write it while `ty` is `"UNK"`. It is left to the app rather than shipped unverified.

```json
{
  "state": {
    "desired": {
      "equipment": {
        "hp_0": {
          "st": 1
        }
      }
    }
  }
}
```

---

## Error Handling

Same as `exo`:

| Condition | Detection | Action |
|---|---|---|
| HTTP 401 | Response code | Trigger token refresh, retry once |
| HTTP 429 | Response code | Re-raise throttle exception before broader service exception |
| Other HTTP error | Response code ≠ 200 | Raise service exception |

## See Also

- [Implementation Notes: hpm](../../implementation/systems/hpm.md) — status lifecycle, design decisions
- [Protocol Reference: exo](exo.md) — the closely related system this one's read/write mechanism mirrors
