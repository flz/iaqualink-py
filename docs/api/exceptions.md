# Exceptions API

Exception classes for error handling.

## Exception Hierarchy

```
AqualinkException (base)
├── AqualinkInvalidParameterException
├── AqualinkServiceException
│   ├── AqualinkServiceUnauthorizedException
│   ├── AqualinkSystemOfflineException
│   └── AqualinkSystemUnsupportedException
├── AqualinkOperationNotSupportedException
└── AqualinkDeviceNotSupported
```

## AqualinkException

::: iaqualink.exception.AqualinkException

## AqualinkInvalidParameterException

::: iaqualink.exception.AqualinkInvalidParameterException

## AqualinkServiceException

::: iaqualink.exception.AqualinkServiceException

## AqualinkServiceUnauthorizedException

::: iaqualink.exception.AqualinkServiceUnauthorizedException

## AqualinkSystemOfflineException

::: iaqualink.exception.AqualinkSystemOfflineException

## AqualinkSystemUnsupportedException

::: iaqualink.exception.AqualinkSystemUnsupportedException

## AqualinkOperationNotSupportedException

::: iaqualink.exception.AqualinkOperationNotSupportedException

## AqualinkDeviceNotSupported

::: iaqualink.exception.AqualinkDeviceNotSupported

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

### Specific Exception Handling

```python
from iaqualink import (
    AqualinkClient,
    AqualinkServiceUnauthorizedException,
    AqualinkServiceException,
    AqualinkSystemOfflineException,
)

try:
    async with AqualinkClient(username, password) as client:
        systems = await client.get_systems()
        system = list(systems.values())[0]

        try:
            await system.update()
        except AqualinkSystemOfflineException:
            print("System is offline")

except AqualinkServiceUnauthorizedException:
    print("Authentication failed - check credentials")
except AqualinkServiceException as e:
    print(f"Service error: {e}")
```

### Retry Logic

```python
import asyncio
from iaqualink import AqualinkServiceException

async def update_with_retry(system, max_retries=3):
    for attempt in range(max_retries):
        try:
            await system.update()
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
from iaqualink import AqualinkSystemOfflineException

async def get_system_status(system):
    try:
        await system.update()
        return {
            "online": True,
            "devices": await system.get_devices()
        }
    except AqualinkSystemOfflineException:
        return {
            "online": False,
            "devices": {}
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
- Rate limiting (though built-in rate limiting should prevent this)

### AqualinkSystemOfflineException

- System is not connected to internet
- System is powered off
- System is in maintenance mode

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
# Good - handle specific errors
try:
    await system.update()
except AqualinkSystemOfflineException:
    print("System offline")
except AqualinkServiceException:
    print("Service error")

# Avoid - too broad
try:
    await system.update()
except Exception:
    print("Something went wrong")
```

### Log Errors

```python
import logging

logger = logging.getLogger(__name__)

try:
    await system.update()
except AqualinkServiceException as e:
    logger.error(f"Failed to update system: {e}", exc_info=True)
```

## See Also

- [Client API](client.md) - Client reference
- [System API](system.md) - System reference
- [Quick Start](../getting-started/quickstart.md) - Getting started
