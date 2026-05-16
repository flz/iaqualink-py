# Systems

iaqualink-py supports multiple Jandy pool system types through a unified interface.

## System Types

The library supports three system types. See the per-system guides for type-specific behaviour including status mapping:

- [iAqua Systems](iaqua.md) — original Jandy iAqualink systems (`iaqualink.net` API)
- [eXO Systems](exo.md) — Zodiac systems with AWS IoT shadow state (`zodiac-io.com` API)
- [i2d Systems](i2d.md) — iQPump variable-speed pumps (`r-api.iaqualink.net` API)

## Discovering Systems

```python
from iaqualink import AqualinkClient

async with AqualinkClient('user@example.com', 'password') as client:
    # Returns dict mapping serial numbers to system objects
    systems = await client.get_systems()

    for serial, system in systems.items():
        print(f"Serial: {serial}")
        print(f"Name: {system.name}")
        print(f"Type: {system.data.get('device_type')}")
```

## System Properties

All systems have these common properties:

```python
# System identification
system.name              # User-friendly name
system.serial            # Unique serial number
system.data              # Raw system data from API

# System status
system.status            # SystemStatus enum value
system.status_translated # Human-readable string, e.g. "Online", "In Progress"
```

See the per-system guides for the full status value mapping: [iAqua](iaqua.md#system-status) · [eXO](exo.md#system-status)

## Updating System State

Systems cache their state and rate-limit API calls to 5-second intervals:

```python
# First update - fetches from API
await system.update()

# Immediate subsequent call - returns cached data
await system.update()

# After 5+ seconds - fetches fresh data
import asyncio
await asyncio.sleep(5)
await system.update()
```

## Getting Devices

Each system manages a collection of devices:

```python
# Get all devices as a dictionary
devices = await system.get_devices()

# Access specific device by name
pool_pump = devices.get('pool_pump')

# Iterate over all devices
for name, device in devices.items():
    print(f"{name}: {device.label}")
```

## Checking System Status

After `refresh()`, inspect `system.status` to determine whether the system
is ready before interacting with its devices:

```python
from iaqualink.system import SystemStatus

await system.refresh()

if system.status == SystemStatus.ONLINE:
    devices = await system.get_devices()
elif system.status == SystemStatus.OFFLINE:
    print(f"System {system.name} is offline")
elif system.status == SystemStatus.SERVICE:
    print(f"System {system.name} is in service mode")
elif system.status == SystemStatus.DISCONNECTED:
    print(f"System {system.name} could not be reached")
```

## System Type Detection

The library automatically selects the correct system implementation:

```python
# System type is detected automatically
systems = await client.get_systems()

# Check system type
for system in systems.values():
    if system.data.get('device_type') == 'iaqua':
        print("This is an iAqua system")
    elif system.data.get('device_type') == 'exo':
        print("This is an eXO system")
```

## Advanced Usage

### Manual System Creation

Typically you don't need to create systems manually, but it's possible:

```python
from iaqualink.systems.iaqua import IaquaSystem

# Create system from data (rarely needed)
system = IaquaSystem.from_data(client, system_data)
```

### Accessing Raw API Data

```python
# Access raw system data
print(system.data)

# After update, check what changed
await system.update()
print(system.data)
```

## Next Steps

- [Devices Guide](devices.md) - Learn about device types
- [Examples](examples.md) - See complete examples
- [API Reference](../api/system.md) - Detailed API documentation
