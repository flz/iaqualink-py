# Client API

The `AqualinkClient` class is the main entry point for interacting with the iAqualink API.

## AqualinkClient

::: iaqualink.client.AqualinkClient

## Usage

### Basic Usage

```python
from iaqualink import AqualinkClient

async with AqualinkClient('user@example.com', 'password') as client:
    systems = await client.get_systems()
```

### Manual Session Management

```python
client = AqualinkClient('user@example.com', 'password')
try:
    await client.login()
    systems = await client.get_systems()
finally:
    await client.close()
```

## Methods

### login()

Authenticate with the iAqualink service.

**Returns:** `None`

**Raises:**
- `AqualinkLoginException` - Authentication failed

### get_systems()

Discover and retrieve all pool systems associated with the account.

**Returns:** `dict[str, AqualinkSystem]` - Dictionary mapping serial numbers to system objects

**Raises:**
- `AqualinkServiceException` - Service error occurred

### close()

Close the HTTP client session.

**Returns:** `None`

## Properties

### username

The username used for authentication.

**Type:** `str`

### password

The password used for authentication.

**Type:** `str`

## Context Manager

The client supports the async context manager protocol:

```python
async with AqualinkClient(username, password) as client:
    # Client is authenticated and ready to use
    systems = await client.get_systems()
# Client is automatically closed
```

## HTTP Client

The client uses `httpx.AsyncClient` with HTTP/2 support for efficient API communication.

## See Also

- [System API](system.md) - System object reference
- [Quick Start](../getting-started/quickstart.md) - Getting started guide
