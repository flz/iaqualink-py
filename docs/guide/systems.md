# Systems

iaqualink-py supports multiple Jandy pool system types through a unified interface.

## System Types

### iAqua Systems

iAqua systems use the iaqualink.net API and are the original Jandy iAqualink systems.

**Characteristics:**
- API endpoint: iaqualink.net
- Authentication via session tokens
- Two-step device refresh (home + devices)
- Commands sent as session requests

### eXO Systems

eXO systems are newer Zodiac systems using the zodiac-io.com API.

**Characteristics:**
- API endpoint: zodiac-io.com
- JWT token authentication
- AWS IoT-style shadow state
- Desired/reported state pattern

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
system.name          # User-friendly name
system.serial        # Unique serial number

# System status
system.online        # Boolean indicating if system is online
system.data          # Raw system data from API

# Last update time
system.last_run_success  # Timestamp of last successful update
```

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

## System Offline Handling

Handle offline systems gracefully:

```python
from iaqualink import AqualinkSystemOfflineException

try:
    await system.update()
except AqualinkSystemOfflineException:
    print(f"System {system.name} is offline")
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
