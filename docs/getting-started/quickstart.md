# Quick Start

This guide will help you get started with iaqualink-py quickly.

## Basic Usage

### Connecting to Your System

```python
from iaqualink import AqualinkClient

async with AqualinkClient('user@example.com', 'password') as client:
    # Discover your pool systems
    systems = await client.get_systems()

    # Get the first system
    system = list(systems.values())[0]
    print(f"Found system: {system.name}")
```

### Getting Devices

```python
from iaqualink.device import AqualinkSensor, AqualinkSwitch

# Get all devices for a system
devices = await system.get_devices()

# Access specific devices
pool_temp = devices.get('pool_temp')
if isinstance(pool_temp, AqualinkSensor):
    print(f"Pool temperature: {pool_temp.value}°F")

spa_heater = devices.get('spa_heater')
if isinstance(spa_heater, AqualinkSwitch):
    print(f"Spa heater: {'ON' if spa_heater.is_on else 'OFF'}")
```

### Controlling Devices

#### Switches and Pumps

```python
# Turn on pool pump
pool_pump = devices.get('pool_pump')
if pool_pump:
    await pool_pump.turn_on()

# Turn off spa heater
spa_heater = devices.get('spa_heater')
if spa_heater:
    await spa_heater.turn_off()
```

#### Lights

```python
from iaqualink.device import AqualinkLight

pool_light = devices.get('aux_3')
if isinstance(pool_light, AqualinkLight):
    await pool_light.turn_on()
```

#### Thermostats

```python
from iaqualink.device import AqualinkClimate

# Set spa temperature
spa_heater = devices.get('spa_set_point')
if isinstance(spa_heater, AqualinkClimate):
    await spa_heater.set_temperature(102)

# Set pool temperature
pool_heater = devices.get('pool_set_point')
if isinstance(pool_heater, AqualinkClimate):
    await pool_heater.set_temperature(82)
```

### Monitoring System Status

```python
# Check if system is online
from iaqualink import AqualinkSensor, SystemStatus

# Refresh system state
await system.refresh()

# Check if system is online
if system.status is SystemStatus.ONLINE:
    print(f"System {system.name} is online")

    # Get all temperature readings
    for device_name, device in devices.items():
        if isinstance(device, AqualinkSensor) and device.value:
            print(f"{device.label}: {device.value}")
```

## Working with Multiple Systems

If you have multiple pool systems:

```python
async with AqualinkClient('user@example.com', 'password') as client:
    systems = await client.get_systems()

    for serial, system in systems.items():
        print(f"System: {system.name} ({serial})")
        print(f"Type: {system.data.get('device_type')}")

        devices = await system.get_devices()
        print(f"Devices: {len(devices)}")
```

## Error Handling

```python
from iaqualink import AqualinkClient
from iaqualink.exception import (
    AqualinkServiceException,
    AqualinkServiceUnauthorizedException,
)

try:
    async with AqualinkClient('user@example.com', 'password') as client:
        systems = await client.get_systems()
except AqualinkServiceUnauthorizedException:
    print("Invalid credentials")
except AqualinkServiceException as e:
    print(f"Service error: {e}")
```

## Next Steps

- [CLI Reference](cli.md) — command-line client for scripting and quick control
- [API Reference](../api/client.md) — `AqualinkClient` class reference
- [Architecture](../contributing/architecture.md) — system/device hierarchy and data flow
- [Protocol Reference](../reference/client.md) — wire-level auth and endpoint details
