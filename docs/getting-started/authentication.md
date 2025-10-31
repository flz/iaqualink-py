# Authentication

iaqualink-py supports both iAqua and eXO system authentication methods.

## Basic Authentication

The simplest way to authenticate is using your email and password:

```python
from iaqualink import AqualinkClient

async with AqualinkClient('user@example.com', 'password') as client:
    systems = await client.get_systems()
```

## Session Management

The library uses context managers to handle session cleanup automatically:

```python
# Recommended: Use context manager for automatic cleanup
async with AqualinkClient(username, password) as client:
    # Your code here
    pass
# Session is automatically closed

# Alternative: Manual session management
client = AqualinkClient(username, password)
try:
    systems = await client.get_systems()
finally:
    await client.close()
```

## System Type Detection

The library automatically detects whether you have an iAqua or eXO system and uses the appropriate authentication method:

### iAqua Systems

- Uses iaqualink.net API
- Authentication returns `session_id` and `authentication_token`
- Credentials passed as query parameters

### eXO Systems

- Uses zodiac-io.com API
- Authentication returns JWT `IdToken`
- Token used in Authorization header
- Automatic token refresh on expiration

## Authentication Errors

Handle authentication errors appropriately:

```python
from iaqualink import AqualinkClient, AqualinkLoginException

try:
    async with AqualinkClient('user@example.com', 'password') as client:
        systems = await client.get_systems()
except AqualinkLoginException as e:
    print(f"Login failed: {e}")
```

## Security Best Practices

!!! warning "Credential Security"
    Never hardcode credentials in your code. Use environment variables or secure configuration files.

```python
import os
from iaqualink import AqualinkClient

username = os.getenv('IAQUALINK_USERNAME')
password = os.getenv('IAQUALINK_PASSWORD')

async with AqualinkClient(username, password) as client:
    systems = await client.get_systems()
```

## HTTP/2 Support

The library uses httpx with HTTP/2 support for improved performance:

```python
# HTTP/2 is enabled by default
# No additional configuration needed
```

## Next Steps

- [Quick Start](quickstart.md) - Start using the library
- [Systems Guide](../guide/systems.md) - Learn about system types
