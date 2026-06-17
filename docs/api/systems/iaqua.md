# iAqua Systems API

iAqua systems use the iaqualink.net API.

## IaquaSystem

::: iaqualink.systems.iaqua.system.IaquaSystem

## IaquaDevice

::: iaqualink.systems.iaqua.device.IaquaDevice

## IaquaIclLight

::: iaqualink.systems.iaqua.device.IaquaIclLight

## IaquaZoneStatus

::: iaqualink.systems.iaqua.device.IaquaZoneStatus

## IaquaHeatPump

::: iaqualink.systems.iaqua.device.IaquaHeatPump

## IaquaHeatPumpMode

::: iaqualink.systems.iaqua.device.IaquaHeatPumpMode

## IaquaHeatPumpStatusSensor

::: iaqualink.systems.iaqua.device.IaquaHeatPumpStatusSensor

## IaquaHeatPumpAlertSensor

::: iaqualink.systems.iaqua.device.IaquaHeatPumpAlertSensor

## Characteristics

### API Endpoint

- **Base URL:** `https://r-api.iaqualink.net`
- **Session URL:** `https://r-api.iaqualink.net/v2/mobile/session.json`
- **API Version:** v2

### Authentication

All session requests use:
- `Authorization: Bearer {idToken}` header (Cognito JWT from login)
- `api_key: {key}` header
- `sessionID={sessionId}` query parameter

### Device Refresh

iAqua systems use a two- or three-step refresh process:

1. **Home data** - Basic system information and OneTouch support flag
2. **Device data** - Detailed device states
3. **OneTouch data** - OneTouch scene states (only when `"onetouch": "true"` in home response)

```python
# Implemented internally by IaquaSystem.update()
await system.update()
```

### Command Format

Commands are sent as session requests with specific command names:

```python
# Example command structure
{
    "command": "set_aux",
    "aux": "1",
    "state": "1"
}
```

## Device Types

### Temperature Sensors

- `pool_temp` - Pool temperature
- `spa_temp` - Spa temperature
- `air_temp` - Air temperature

### Pumps

- `pool_pump` - Main pool pump
- `spa_pump` - Spa pump
- `pool_filter_pump` - Filter pump

### Heaters

- `pool_heater` - Pool heater
- `spa_heater` - Spa heater
- `solar_heater` - Solar heater

### Thermostats

- `pool_set_point` - Pool temperature setpoint
- `spa_set_point` - Spa temperature setpoint

Temperature ranges:
- **Fahrenheit:** 34°F - 104°F
- **Celsius:** 1°C - 40°C

When a heat pump is paired (see Heat Pump below), `pool_set_point` and `spa_set_point` transparently route their writes through the heat pump's `setpoint_hpm_temp` command instead of `set_temps` — same device, same API, different command on the wire.

### Heat Pump (HPM)

Optional sub-system, only present when a heat pump is paired with the iQ20 controller (`heatpump_info.isheatpumpPresent` in the home response). Distinct from the relay-based heaters above and from the standalone AWS-IoT-shadow heat pump device (out of scope for this system).

- `heatpump` - Enable/disable switch. Class: `IaquaHeatPump`.
- `heatpump_mode` - Heat/chill mode picker. Only present when the paired unit supports chill mode. Class: `IaquaHeatPumpMode`.
- `heatpump_status` - Raw operational status (`off`/`enabled`/`on`). Class: `IaquaHeatPumpStatusSensor`.
- `heatpump_alert` - Fault code, if any. Only present once an HPM command response has supplied one. Class: `IaquaHeatPumpAlertSensor`.
- `pool_chill_set_point` - Pool chill (cooling) set point. Only present when chill mode is available. Uses the existing `IaquaSetPoint` class.

### Lights

- `pool_light` - Pool light
- `spa_light` - Spa light

### ICL Lights

- `icl_zone_1` through `icl_zone_4` — Per-zone RGBW LED control (IntelliCenter Light sub-system). Only present when the controller reports ICL zones as non-absent. Class: `IaquaIclLight`.

### Auxiliary Devices

- `aux_1` through `aux_7` - Configurable auxiliary switches

### OneTouch Scenes

- `onetouch_1` through `onetouch_N` - Saved scenes (only present when system advertises `"onetouch": "true"` in the home response)

OneTouch scenes have toggle semantics: sending the command flips the scene state. `turn_on()` activates an inactive scene; `turn_off()` deactivates an active one.

### Chemistry Sensors

- `ph` - pH level (0-14)
- `orp` - Oxidation-reduction potential (mV)
- `salt` - Salt level (ppm)

### Status Sensors

- `freeze_protection` - Freeze protection status

## Usage Example

```python
from iaqualink import AqualinkClient

async with AqualinkClient(username, password) as client:
    systems = await client.get_systems()

    # Find iAqua system
    for system in systems.values():
        if system.data.get('device_type') == 'iaqua':
            print(f"Found iAqua system: {system.name}")

            devices = await system.get_devices()

            # Control pool pump
            pool_pump = devices.get('pool_pump')
            await pool_pump.turn_on()

            # Set spa temperature
            spa_thermostat = devices.get('spa_set_point')
            await spa_thermostat.set_temperature(102)
```

## API Details

### Rate Limiting

5-second minimum interval between updates (enforced by base class).

### Data Format

Device data includes:
```python
{
    "name": "device_name",
    "label": "User Label",
    "state": "1",  # String representation
    "type": "device_type",
    # ... additional fields
}
```

## See Also

- [System API](../system.md) - Base system reference
- [Device API](../device.md) - Base device reference
- [eXO Systems](exo.md) - Compare with eXO systems
