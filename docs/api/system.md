# System API

The `AqualinkSystem` class represents a pool/spa control system.

## AqualinkSystem

::: iaqualink.system.AqualinkSystem

## Usage

### Getting Systems

```python
async with AqualinkClient(username, password) as client:
    systems = await client.get_systems()
    system = list(systems.values())[0]
```

### Updating State

```python
# Update system state
await system.update()

# Check if online
from iaqualink.system import SystemStatus

if system.status is SystemStatus.ONLINE:
    print(f"System {system.name} is online")
```

### Getting Devices

```python
# Get all devices
devices = await system.get_devices()

# Access specific device
pool_pump = devices.get('pool_pump')
```

## Properties

### name

User-friendly name of the system.

**Type:** `str`

### serial

Unique serial number identifying the system.

**Type:** `str`

### status

Current connectivity state of the system.

**Type:** `SystemStatus`

One of:

- `SystemStatus.ONLINE` — last update succeeded
- `SystemStatus.OFFLINE` — system is definitively offline
- `SystemStatus.UNKNOWN` — never successfully fetched, or last update raised a service error

### data

Raw system data from the API.

**Type:** `dict[str, Any]`

### last_run_success

Timestamp of the last successful update.

**Type:** `float | None`

## Methods

### update()

Fetch the latest system state from the API.

**Returns:** `None`

**Raises:**
- `AqualinkSystemOfflineException` - System is offline
- `AqualinkServiceException` - Service error occurred

### get_devices()

Get all devices associated with this system.

**Returns:** `dict[str, AqualinkDevice]` - Dictionary mapping device names to device objects

**Raises:**
- `AqualinkServiceException` - Service error occurred

## UnsupportedSystem

::: iaqualink.system.UnsupportedSystem

Returned by `AqualinkSystem.from_data()` when the `device_type` is not recognised.
`get_devices()` returns `{}` and `update()` is a no-op. `supported` is `False`.

```python
from iaqualink.system import UnsupportedSystem

systems = await client.get_systems()
for system in systems.values():
    if not system.supported:
        print(f"{system.name} uses an unrecognised device type")
```

## System Types

The library includes two system implementations:

### IaquaSystem

For iAqua systems using iaqualink.net API.

**Device Type:** `"iaqua"`

### ExoSystem

For eXO systems using zodiac-io.com API.

**Device Type:** `"exo"`

## Factory Method

### from_data()

Create a system instance from API data.

```python
system = AqualinkSystem.from_data(client, system_data)
```

**Parameters:**
- `aqualink` (`AqualinkClient`) - The client instance
- `data` (`dict[str, Any]`) - System data from API

**Returns:** `AqualinkSystem` - Appropriate system subclass instance

## See Also

- [Client API](client.md) - Client reference
- [Device API](device.md) - Device reference
- [iAqua Systems](iaqua.md) - iAqua-specific details
- [eXO Systems](exo.md) - eXO-specific details
