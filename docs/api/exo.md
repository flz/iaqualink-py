# eXO Systems API

eXO systems use the zodiac-io.com API with AWS IoT-style shadow state.

## ExoSystem

::: iaqualink.systems.exo.system.ExoSystem

## ExoDevice

::: iaqualink.systems.exo.device.ExoDevice

## Characteristics

### API Endpoint

- **Base URL:** `https://r-api.zodiac-io.com`
- **API Type:** AWS IoT Device Shadow

### Authentication

```python
# Authentication returns JWT token
{
    "userPoolOAuth": {
        "IdToken": "eyJ..."
    }
}
```

Token is used in Authorization header:
```
Authorization: IdToken
```

### Token Refresh

Tokens are automatically refreshed on 401 responses.

### State Management

eXO systems use AWS IoT shadow state pattern:

```python
{
    "state": {
        "reported": {
            # Current device states
        },
        "desired": {
            # Desired device states (for commands)
        }
    }
}
```

### Command Format

Commands update the desired state:

```python
# Example command
{
    "state": {
        "desired": {
            "equipment": {
                "0": {
                    "desiredState": 1
                }
            }
        }
    }
}
```

## Device Types

### Temperature Sensors

- `pool_temp` - Pool temperature
- `spa_temp` - Spa temperature
- `air_temp` - Air temperature

### Equipment

Equipment is identified by numeric indices (0, 1, 2, etc.) with types:

- **Pumps** (`type: 1`)
    - Pool pump
    - Spa pump
    - Other circulation pumps

- **Heaters** (`type: 2`)
    - Pool heater
    - Spa heater

- **Lights** (`type: 3`)
    - Pool light
    - Spa light

- **Auxiliary** (`type: 4`)
    - Generic on/off switches

### Thermostats

- `pool_set_point` - Pool temperature setpoint
- `spa_set_point` - Spa temperature setpoint

Temperature ranges:
- **Fahrenheit:** 40°F - 104°F
- **Celsius:** 4°C - 40°C

### Chemistry Sensors

- `ph` - pH level
- `orp` - Oxidation-reduction potential (mV)

### Status

- `freeze_protection` - Freeze protection status
- System online status

## Usage Example

```python
from iaqualink import AqualinkClient

async with AqualinkClient(username, password) as client:
    systems = await client.get_systems()

    # Find eXO system
    for system in systems.values():
        if system.data.get('device_type') == 'exo':
            print(f"Found eXO system: {system.name}")

            devices = await system.get_devices()

            # Control equipment
            pool_pump = devices.get('pool_pump')
            if pool_pump:
                await pool_pump.turn_on()

            # Set temperature
            spa_thermostat = devices.get('spa_set_point')
            if spa_thermostat:
                await spa_thermostat.set_temperature(102)
```

## API Details

### Rate Limiting

5-second minimum interval between updates (enforced by base class).

### Shadow State Structure

```python
{
    "state": {
        "reported": {
            "equipment": {
                "0": {
                    "name": "Pool Pump",
                    "state": 1,
                    "type": 1
                }
            },
            "temperatures": {
                "0": {
                    "name": "Pool",
                    "current": 78,
                    "target": 82
                }
            }
        }
    }
}
```

### Equipment Types

| Type | Description |
|------|-------------|
| 1    | Pump        |
| 2    | Heater      |
| 3    | Light       |
| 4    | Auxiliary   |

### Device Naming

Devices are automatically named based on their equipment type and position:

```python
# Examples
"pool_pump"     # First pump
"spa_pump"      # Second pump (if spa-related)
"pool_heater"   # First heater
"pool_light"    # First light
"aux_1"         # First auxiliary
```

## Differences from iAqua

| Feature | iAqua | eXO |
|---------|-------|-----|
| Authentication | Session tokens | JWT tokens |
| State updates | Two API calls | Single shadow state |
| Commands | Session requests | Desired state |
| Device IDs | Named | Numeric indices |
| Token refresh | Manual | Automatic |

## See Also

- [System API](system.md) - Base system reference
- [Device API](device.md) - Base device reference
- [iAqua Systems](iaqua.md) - Compare with iAqua systems
