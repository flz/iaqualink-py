# iAqua Systems API

iAqua systems use the iaqualink.net API.

## IaquaSystem

::: iaqualink.systems.iaqua.system.IaquaSystem

## IaquaDevice

::: iaqualink.systems.iaqua.device.IaquaDevice

## Characteristics

### API Endpoint

- **Base URL:** `https://support.iaqualink.com`
- **API Version:** v1

### Authentication

```python
# Authentication returns session tokens
{
    "session_id": "...",
    "authentication_token": "..."
}
```

Credentials are passed as query parameters in API requests.

### Device Refresh

iAqua systems use a two-step refresh process:

1. **Home data** - Basic system information
2. **Device data** - Detailed device states

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
- **Fahrenheit:** 32°F - 104°F
- **Celsius:** 0°C - 40°C

### Lights

- `pool_light` - Pool light
- `spa_light` - Spa light

### Auxiliary Devices

- `aux_1` through `aux_7` - Configurable auxiliary switches

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

- [System API](system.md) - Base system reference
- [Device API](device.md) - Base device reference
- [eXO Systems](exo.md) - Compare with eXO systems
