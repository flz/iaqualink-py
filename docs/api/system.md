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
if system.online:
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

### online

Whether the system is currently online.

**Type:** `bool`

### data

Raw system data from the API.

**Type:** `dict[str, Any]`

### last_run_success

Timestamp of the last successful update.

**Type:** `float | None`

## Methods

### update()

Fetch the latest system state from the API.

Updates are rate-limited to once every 5 seconds. Calls within this window return cached data.

**Returns:** `None`

**Raises:**
- `AqualinkSystemOfflineException` - System is offline
- `AqualinkServiceException` - Service error occurred

### get_devices()

Get all devices associated with this system.

**Returns:** `dict[str, AqualinkDevice]` - Dictionary mapping device names to device objects

**Raises:**
- `AqualinkServiceException` - Service error occurred

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

## Rate Limiting

Systems implement automatic rate limiting with a minimum interval of 5 seconds between API calls:

```python
# First call - fetches from API
await system.update()

# Immediate call - returns cached data
await system.update()

# After 5+ seconds - fetches fresh data
await asyncio.sleep(5)
await system.update()
```

## See Also

- [Client API](client.md) - Client reference
- [Device API](device.md) - Device reference
- [iAqua Systems](iaqua.md) - iAqua-specific details
- [eXO Systems](exo.md) - eXO-specific details
