# Exceptions API

Exception classes for error handling.

## Exception Hierarchy

```
AqualinkException (base)
├── AqualinkInvalidParameterException
├── AqualinkServiceException
│   ├── AqualinkServiceUnauthorizedException
│   └── AqualinkServiceThrottledException
└── AqualinkOperationNotSupportedException
```

## AqualinkException

::: iaqualink.exception.AqualinkException

## AqualinkInvalidParameterException

::: iaqualink.exception.AqualinkInvalidParameterException

## AqualinkServiceException

::: iaqualink.exception.AqualinkServiceException

## AqualinkServiceUnauthorizedException

::: iaqualink.exception.AqualinkServiceUnauthorizedException

## AqualinkSystemUnsupportedException

!!! warning "Deprecated"
    This exception is no longer raised. Unknown device types now return
    [`UnsupportedSystem`](system.md#unsupportedsystem) instead.
    `AqualinkSystemUnsupportedException` will be removed in a future release.
    Importing it emits a `DeprecationWarning`.

## AqualinkOperationNotSupportedException

::: iaqualink.exception.AqualinkOperationNotSupportedException

## Usage Examples

### Basic Error Handling

```python
from iaqualink import (
    AqualinkClient,
    AqualinkException,
)

try:
    async with AqualinkClient(username, password) as client:
        systems = await client.get_systems()
except AqualinkException as e:
    print(f"Error: {e}")
```

### System Status Check

System availability is exposed through `system.status` rather than exceptions.
Check it after `refresh()` before interacting with devices:

```python
from iaqualink import AqualinkClient
from iaqualink.system import SystemStatus

async with AqualinkClient(username, password) as client:
    systems = await client.get_systems()
    system = list(systems.values())[0]

    await system.refresh()
    if system.status in (SystemStatus.ONLINE, SystemStatus.CONNECTED):
        devices = await system.get_devices()
    else:
        print(f"System not ready: {system.status_translated}")
```

### Retry Logic

```python
import asyncio
from iaqualink import AqualinkServiceException

async def refresh_with_retry(system, max_retries=3):
    for attempt in range(max_retries):
        try:
            await system.refresh()
            return
        except AqualinkServiceException as e:
            if attempt < max_retries - 1:
                wait = 2 ** attempt  # Exponential backoff
                print(f"Retry {attempt + 1}/{max_retries} in {wait}s")
                await asyncio.sleep(wait)
            else:
                raise
```

### Graceful Degradation

```python
from iaqualink.system import SystemStatus

async def get_system_status(system):
    await system.refresh()
    if system.status in (SystemStatus.ONLINE, SystemStatus.CONNECTED):
        return {
            "online": True,
            "status": system.status_translated,
            "devices": await system.get_devices(),
        }
    return {
        "online": False,
        "status": system.status_translated,
        "devices": {},
    }
```

## Exception Properties

All exceptions include:

### message

Human-readable error message.

**Type:** `str`

### args

Exception arguments tuple.

**Type:** `tuple`

## When Exceptions Are Raised

### AqualinkServiceUnauthorizedException

- Invalid username or password
- Account locked or suspended
- API authentication endpoint unavailable
- Session token expired

### AqualinkInvalidParameterException

- Invalid temperature value
- Invalid device parameter
- Out of range values

### AqualinkServiceException

- API request failed
- Invalid response format
- Network connectivity issues
- Rate limiting (HTTP 429 from the server)

## Best Practices

### Always Use Context Managers

```python
# Good - automatic cleanup
async with AqualinkClient(username, password) as client:
    systems = await client.get_systems()

# Avoid - manual cleanup needed
client = AqualinkClient(username, password)
try:
    systems = await client.get_systems()
finally:
    await client.close()
```

### Catch Specific Exceptions

```python
from iaqualink import AqualinkServiceUnauthorizedException, AqualinkServiceException

# Good - handle specific errors
try:
    async with AqualinkClient(username, password) as client:
        systems = await client.get_systems()
except AqualinkServiceUnauthorizedException:
    print("Authentication failed")
except AqualinkServiceException:
    print("Service error")

# Avoid - too broad
try:
    async with AqualinkClient(username, password) as client:
        systems = await client.get_systems()
except Exception:
    print("Something went wrong")
```

### Log Errors

```python
import logging

logger = logging.getLogger(__name__)

try:
    await system.refresh()
except AqualinkServiceException as e:
    logger.error(f"Failed to refresh system: {e}", exc_info=True)
```

## See Also

- [Client API](client.md) - Client reference
- [System API](system.md) - System reference
- [Quick Start](../getting-started/quickstart.md) - Getting started
