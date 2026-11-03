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

## Custom Service Contract: `control_swc_boost`

`IaquaSystem.control_swc_boost(control, boosthrs=None, boostmode=None)` is
the single validated entry point for all 4 SWC boost actions
(`start`/`stop`/`pause`/`resume`). The 4 `swc_boost_start`/`stop`/`pause`/
`resume` button entities already cover the common, no-input case (pressing
`swc_boost_start` repeats the last-known hours/mode). A custom service is
only needed for the one case buttons can't handle: starting a boost with
*new* hours/mode — see [Boost control](../implementation/systems/iaqua.md).
The built-in `iaqualink` integration doesn't expose this as a custom service
yet. If you're implementing that in `home-assistant/core`, match this
contract so the service, its docs, and this library's semantics stay aligned:

- Service: `iaqualink.control_swc_boost`
- Target: `entity_id` of one of the `swc_boost_*` button entities — the
  integration resolves the owning `IaquaSystem` the same way it does for any
  other iaqualink entity/service call.
- Fields:
  - `control` (string, required, one of `start` / `stop` / `pause` /
    `resume`) — must match `IaquaBoostControl`'s wire values exactly.
  - `hours` (int, optional, 1–24) — forwarded as `boosthrs`; required when
    `control` is `start`. `control_swc_boost` re-validates range and raises
    `AqualinkInvalidParameterException` if out of bounds or missing on start.
  - `mode` (string, optional, one of `pool` / `spillover`) — forwarded as
    `boostmode`; required when `control` is `start`. Must match
    `IaquaBoostMode`'s wire values exactly; don't rename or translate them in
    the service schema.
- Call: `await system.control_swc_boost(control, boosthrs=hours, boostmode=mode)`.
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
