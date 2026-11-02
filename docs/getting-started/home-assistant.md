# Home Assistant

The primary way most users interact with iaqualink-py is through the built-in Home Assistant integration.

## Built-in Integration

iaqualink-py is included in Home Assistant core as the `iaqualink` integration. No separate installation is required if you are running Home Assistant.

**Integration source:** [homeassistant/components/iaqualink](https://github.com/home-assistant/core/tree/dev/homeassistant/components/iaqualink)

## Setting Up in Home Assistant

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for **iAqualink**
3. Enter your Jandy iAqualink account credentials (the same login you use for the iAqualink mobile app)
4. Home Assistant will discover your pool systems and add their devices automatically

## Supported Systems

| System type | Description |
|---|---|
| iAqua (`iaqua`) | Original Jandy iAqualink pool/spa controllers (IQ20 / IQ900) |
| eXO (`exo`) | Zodiac EXO salt water chlorinators |
| iQPump (`i2d`) | Jandy iQPump variable-speed pump controllers |

## Supported Devices

Device availability depends on your system type and hardware configuration. Common entities include:

- Pool and spa temperature sensors
- Air temperature sensor
- Thermostats (pool/spa set points)
- Pump and heater switches
- Lights
- Auxiliary switches
- Water chemistry sensors (pH, ORP, salinity — eXO)
- Variable speed pump control (i2d)

## Custom Service Contract: `set_swc_boost`

`IaquaSystem.set_swc_boost(boosthrs, boostmode)` is the one SWC boost action
that needs user-supplied values (duration + circuit) beyond what a stateless
`ButtonEntity` press can carry — see [`swc_boost_start`/`stop`/`pause`/`resume`
buttons](../api/systems/iaqua.md). The built-in `iaqualink` integration
doesn't expose this as a custom service yet. If you're implementing that in
`home-assistant/core`, match this contract so the service, its docs, and this
library's semantics stay aligned:

- Service: `iaqualink.set_swc_boost`
- Target: `entity_id` of one of the `swc_boost_*` button entities — the
  integration resolves the owning `IaquaSystem` the same way it does for any
  other iaqualink entity/service call.
- Fields:
  - `boosthrs` (int, required, 1–24) — forwarded as-is; `set_swc_boost`
    re-validates range and raises `AqualinkInvalidParameterException` if out
    of bounds.
  - `boostmode` (string, required, one of `pool` / `spillover`) — must match
    `IaquaBoostMode`'s wire values exactly; don't rename or translate them in
    the service schema.
- Call: `await system.set_swc_boost(boosthrs, boostmode)`.
- Errors: `AqualinkInvalidParameterException` should surface as a HA
  `ServiceValidationError` carrying its message.

This is a spec for that future `home-assistant/core` PR — this repo doesn't
implement HA services itself.

## Troubleshooting

If your system is not discovered or devices are missing, check:

- Your iAqualink app credentials work in the official mobile app
- Your pool controller is online and reachable
- The Home Assistant integration logs for errors (enable debug logging if needed)

For bugs in the HA integration itself, file issues against [home-assistant/core](https://github.com/home-assistant/core).
For bugs in this library, file issues against [flz/iaqualink-py](https://github.com/flz/iaqualink-py).

## Programmatic Use

If you want to use iaqualink-py directly from Python (outside of Home Assistant), see [Programmatic Use](quickstart.md).
