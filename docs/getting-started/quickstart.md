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
# Get all devices for a system
devices = await system.get_devices()

# Access specific devices
pool_temp = devices.get('pool_temp')
if pool_temp:
    print(f"Pool temperature: {pool_temp.state}°F")

spa_heater = devices.get('spa_heater')
if spa_heater:
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
# Toggle pool light
pool_light = devices.get('aux_3')
if pool_light:
    await pool_light.toggle()
```

#### Thermostats

```python
# Set spa temperature
spa_thermostat = devices.get('spa_set_point')
if spa_thermostat:
    await spa_thermostat.set_temperature(102)

# Set pool temperature
pool_thermostat = devices.get('pool_set_point')
if pool_thermostat:
    await pool_thermostat.set_temperature(82)
```

### Monitoring System Status

```python
# Update system state
await system.update()

# Check if system is online
if system.online:
    print(f"System {system.name} is online")

    # Get all temperature readings
    for device_name, device in devices.items():
        if 'temp' in device_name and device.state:
            print(f"{device.label}: {device.state}°")
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

## Rate Limiting

The library automatically rate-limits updates to once every 5 seconds per system to respect API limits. Subsequent calls within this window return cached data.

```python
# First call - fetches from API
await system.update()

# Immediate second call - returns cached data
await system.update()

# After 5+ seconds - fetches fresh data
await asyncio.sleep(5)
await system.update()
```

## Error Handling

```python
from iaqualink import (
    AqualinkClient,
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

- [Authentication](authentication.md) - Learn about authentication details
- [Systems Guide](../guide/systems.md) - Deep dive into systems
- [Devices Guide](../guide/devices.md) - Learn about device types
- [Examples](../guide/examples.md) - See more complete examples
