# i2d Systems (iQPump)

i2d systems are Jandy iQPump variable-speed pump controllers using the `r-api.iaqualink.net` control API.

## Overview

| Property | Value |
|----------|-------|
| `device_type` | `i2d` |
| API host | `r-api.iaqualink.net` |
| Authentication | Bearer `IdToken` + `api_key` header |
| Update call | Single `POST /v2/devices/{serial}/control.json` with `command=/alldata/read` |
| Write commands | Same endpoint with `command=/{key}/write`, `params=value={val}` |

## System Status

Status is derived from the `alldata.opmode` field in the response.

### Status values

| Condition | `SystemStatus` |
|-----------|----------------|
| `opmode` present and `<= 3` | `CONNECTED` |
| `opmode` present and `> 3` | `SERVICE` |
| `opmode` absent, `updateprogress` not `"0"` / `"0/0"` | `FIRMWARE_UPDATE` |
| `opmode` absent, `updateprogress` is `"0"` or `"0/0"` | `UNKNOWN` |
| Device offline | `OFFLINE` |
| Network / HTTP error (non-401, non-429) | `DISCONNECTED` |
| HTTP 429 (throttled) | `UNKNOWN` |

### Status lifecycle

```python
from iaqualink.system import SystemStatus

await system.refresh()

if system.status == SystemStatus.CONNECTED:
    devices = await system.get_devices()
elif system.status == SystemStatus.OFFLINE:
    print(f"Pump {system.name} is offline")
elif system.status == SystemStatus.SERVICE:
    print(f"Pump {system.name} is in service mode")
elif system.status == SystemStatus.FIRMWARE_UPDATE:
    print(f"Pump {system.name} is updating firmware")
```

## Device Types

### Pump (`I2dPump`)

The main pump device. Key is always `"iqpump"`.

```python
pump = devices["iqpump"]

# On/off
await pump.turn_on()   # CUSTOM mode
await pump.turn_off()  # STOP mode

# Presets
print(pump.supported_presets)    # ['SCHEDULE', 'CUSTOM', 'STOP']
print(pump.current_preset)       # 'SCHEDULE', 'CUSTOM', 'STOP', or read-only mode name
await pump.set_preset("CUSTOM")

# Speed percentage (0–100, maps to globalrpmmin–globalrpmmax, rounded to 25 RPM)
await pump.set_speed_percentage(75)

# State
print(pump.state)    # opmode wire value: '0'=SCHEDULE, '1'=CUSTOM, '2'=STOP, …
print(pump.is_on)    # True when runstate == 'on'
```

### Numeric Settings (`I2dNumber`)

Writable numeric values with range and step validation.

```python
# RPM settings
custom_rpm = devices["customspeedrpm"]
print(custom_rpm.current_value)   # e.g. 1500.0
print(custom_rpm.min_value)       # live from globalrpmmin
print(custom_rpm.max_value)       # live from globalrpmmax
await custom_rpm.set_value(2000)  # raises if out of range or not step-aligned

# Global RPM bounds
await devices["globalrpmmin"].set_value(600)
await devices["globalrpmmax"].set_value(3450)

# Timer/period settings (values in seconds)
await devices["quickcleanperiod"].set_value(1800)  # 30 min
await devices["countdownperiod"].set_value(7200)   # 2 hours

# Temperature (°C)
await devices["freezeprotectsetpointc"].set_value(4)
```

**RPM number keys:** `globalrpmmin`, `globalrpmmax`, `customspeedrpm`, `primingrpm`, `quickcleanrpm`, `freezeprotectrpm`, `countdownrpm`

**Optional RPM numbers** (only present on hardware with relay outputs): `relayK1Rpm`, `relayK2Rpm`

**Period/timer keys:** `customspeedtimer`, `primingperiod`, `quickcleanperiod`, `freezeprotectperiod`, `countdownperiod`, `timeoutperiod`

**Temperature key:** `freezeprotectsetpointc`

### Switch (`I2dSwitch`)

Binary on/off settings.

```python
fp = devices["freezeprotectenable"]
print(fp.is_on)      # True / False
await fp.turn_on()
await fp.turn_off()
```

**Switch keys:** `freezeprotectenable`

### Sensors (`I2dSensor`)

Read-only telemetry from the pump's motor data, timers, and system metadata.

```python
print(devices["speed"].state)          # current RPM, e.g. "1500"
print(devices["power"].state)          # watts, e.g. "180"
print(devices["temperature"].state)    # motor temp in °F, e.g. "110"
print(devices["horsepower"].state)     # e.g. "1.65"

# Remaining-time counters (seconds, decrement while mode is active)
print(devices["primingtimer"].state)
print(devices["quickcleantimer"].state)
print(devices["countdowntimer"].state)
print(devices["timeouttimer"].state)

# Schedule state ("-1" = no active span)
print(devices["currentspan"].state)

# WiFi
print(devices["wifistate"].state)  # e.g. "connected"
print(devices["wifissid"].state)   # e.g. "MyNetwork"

# Firmware metadata
print(devices["fwversion"].state)       # e.g. "1.5.2"
print(devices["updateprogress"].state)  # e.g. "0" or "50/100"
print(devices["updateflag"].state)      # e.g. "0"
```

### Binary Sensor (`I2dBinarySensor`)

Read-only binary flags.

```python
fp_status = devices["freezeprotectstatus"]
print(fp_status.is_on)   # True when active
print(fp_status.state)   # "on" / "off"
```

**Binary sensor keys:** `freezeprotectstatus`

## Usage Example

```python
from iaqualink import AqualinkClient
from iaqualink.system import SystemStatus

async with AqualinkClient('user@example.com', 'password') as client:
    systems = await client.get_systems()

    for system in systems.values():
        if system.data.get('device_type') == 'i2d':
            await system.refresh()

            if system.status != SystemStatus.CONNECTED:
                print(f"Pump not ready: {system.status_translated}")
                continue

            devices = await system.get_devices()
            pump = devices["iqpump"]

            # Run at 75% speed
            await pump.set_speed_percentage(75)

            # Check current RPM
            print(f"Speed: {devices['speed'].state} RPM")
            print(f"Power: {devices['power'].state} W")
```

## See Also

- [Getting Started: i2d](../getting-started/i2d.md) — API overview and device inventory
- [Protocol Reference](../reference/i2d.md) — wire-level protocol documentation
- [API Reference](../api/i2d.md) — class and method reference
