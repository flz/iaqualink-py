# Architecture

This document describes the internal architecture of iaqualink-py.

## Overview

The library follows a plugin-style architecture with base classes and system-specific implementations. This design allows supporting multiple API types (iAqua and eXO) through a unified interface.

## Core Components

### 1. AqualinkClient

**Location:** `src/iaqualink/client.py`

The entry point for all interactions with the iAqualink API.

**Responsibilities:**
- Authentication (both iAqua and eXO)
- HTTP client management (httpx with HTTP/2)
- System discovery
- Session management

**Key Features:**
- Context manager support for automatic cleanup
- Automatic system type detection
- Token/session management

### 2. AqualinkSystem

**Location:** `src/iaqualink/system.py`

Base class for pool systems using a registry pattern.

**Responsibilities:**
- Device management
- State polling and caching
- Rate limiting (5-second minimum interval)
- Online/offline status tracking

**Design Pattern: Subclass Registry**

```python
class AqualinkSystem:
    _subclasses: dict[str, type[Self]] = {}

    def __init_subclass__(cls, **kwargs):
        """Register subclass by NAME attribute."""
        if hasattr(cls, 'NAME'):
            cls._subclasses[cls.NAME] = cls

    @classmethod
    def from_data(cls, aqualink, data):
        """Factory method - dispatches to correct subclass."""
        device_type = data.get('device_type')
        subclass = cls._subclasses.get(device_type)
        return subclass(aqualink, data)
```

**Implementations:**
- **IaquaSystem** - `NAME = "iaqua"`
- **ExoSystem** - `NAME = "exo"`

### 3. AqualinkDevice

**Location:** `src/iaqualink/device.py`

Base class for all devices using inheritance hierarchy.

**Hierarchy:**

```
AqualinkDevice (base)
├── AqualinkSensor (read-only)
│   └── AqualinkBinarySensor (on/off state)
│       └── AqualinkSwitch (controllable)
│           ├── AqualinkLight (toggle)
│           └── AqualinkThermostat (temperature)
```

**Responsibilities:**
- Device state management
- Command execution
- Type-specific behavior

## System Implementations

### iAqua Systems

**Location:** `src/iaqualink/systems/iaqua/`

**API Characteristics:**
- Endpoint: iaqualink.net
- Auth: Session tokens (session_id, authentication_token)
- Two API calls for updates:
    - `get_home` - System info
    - `get_devices` - Device states
- Commands: Session requests with command names

**Key Files:**
- `system.py` - IaquaSystem implementation
- `device.py` - iAqua device classes

### eXO Systems

**Location:** `src/iaqualink/systems/exo/`

**API Characteristics:**
- Endpoint: zodiac-io.com
- Auth: JWT IdToken
- Single shadow state API (AWS IoT style)
- State: desired/reported pattern
- Automatic token refresh on 401

**Key Files:**
- `system.py` - ExoSystem implementation
- `device.py` - eXO device classes

## Data Flow

### Authentication Flow

```
User → AqualinkClient(username, password)
      → async with client (calls login())
      → Detect API type from response
      → Store credentials (session_id or IdToken)
```

### System Discovery Flow

```
client.get_systems()
      → Fetch systems from API
      → For each system:
          → Extract device_type
          → AqualinkSystem.from_data()
          → Registry lookup by device_type
          → Instantiate correct subclass
      → Return dict[serial, system]
```

### Device Refresh Flow

```
system.update()
      → Check rate limit (MIN_SECS_TO_REFRESH = 5)
      → If cached, return immediately
      → Fetch from API (system-specific)
      → Parse response
      → Update device states
      → Cache timestamp
```

### Command Flow

```
device.turn_on()
      → Build command (system-specific)
      → Send to API via system
      → Return (state updates on next poll)
```

## Rate Limiting

Systems implement rate limiting to respect API limits:

```python
MIN_SECS_TO_REFRESH = 5.0

async def update(self):
    now = time.time()
    if self.last_run_success and \
       (now - self.last_run_success) < MIN_SECS_TO_REFRESH:
        return  # Use cached data

    # Fetch from API
    await self._update_impl()
    self.last_run_success = now
```

## Type System

The library uses modern Python type hints (3.12+):

```python
from typing import Self, Any
from collections.abc import Awaitable

class AqualinkSystem:
    def __init__(self, aqualink: AqualinkClient, data: dict[str, Any]):
        ...

    @classmethod
    def from_data(
        cls,
        aqualink: AqualinkClient,
        data: dict[str, Any]
    ) -> Self:
        ...
```

## Testing Architecture

**Base Class:** `TestBase` in `tests/base.py`

**Structure:**
```
tests/
├── base.py                    # TestBase with common setup
├── test_client.py             # Client tests
├── test_system.py             # System tests
├── test_device.py             # Device tests
└── systems/
    ├── iaqua/
    │   ├── base_test_system.py   # Abstract iAqua tests
    │   ├── base_test_device.py   # Abstract device tests
    │   └── test_*.py             # Concrete tests
    └── exo/
        ├── base_test_system.py
        ├── base_test_device.py
        └── test_*.py
```

**Mocking:** Uses `respx` for HTTP mocking

## Error Handling

**Exception Hierarchy:**

```
AqualinkException
└── AqualinkServiceException
    ├── AqualinkLoginException
    └── AqualinkSystemOfflineException
```

**Location:** `src/iaqualink/exception.py`

## Adding New System Types

To support a new system type:

### 1. Create Directory Structure

```bash
mkdir -p src/iaqualink/systems/newsystem
touch src/iaqualink/systems/newsystem/__init__.py
touch src/iaqualink/systems/newsystem/system.py
touch src/iaqualink/systems/newsystem/device.py
```

### 2. Implement System Class

```python
# src/iaqualink/systems/newsystem/system.py
from iaqualink.system import AqualinkSystem

class NewSystem(AqualinkSystem):
    NAME = "newsystem"  # Must match device_type from API

    async def _update_impl(self):
        """Fetch and parse system state."""
        # Implementation here
        pass

    async def _send_command(self, device, command):
        """Send command to device."""
        # Implementation here
        pass
```

### 3. Implement Device Classes

```python
# src/iaqualink/systems/newsystem/device.py
from iaqualink.device import (
    AqualinkDevice,
    AqualinkSwitch,
    AqualinkThermostat,
)

class NewDevice(AqualinkDevice):
    """Base device for new system."""
    pass

class NewSwitch(NewDevice, AqualinkSwitch):
    """Switch for new system."""
    pass
```

### 4. Register in __init__.py

```python
# src/iaqualink/systems/newsystem/__init__.py
from .system import NewSystem
from .device import NewDevice, NewSwitch

__all__ = ["NewSystem", "NewDevice", "NewSwitch"]
```

### 5. Add Tests

Follow existing test structure in `tests/systems/newsystem/`.

### 6. Update Documentation

Add system-specific documentation in `docs/api/newsystem.md`.

## Dependencies

**Runtime:**
- `httpx[http2]>=0.27.0` - HTTP client with HTTP/2

**Development:**
- `ruff>=0.11.2` - Linting and formatting
- `mypy>=1.15.0` - Type checking
- `pytest>=8.3.5` - Testing
- `respx>=0.22.0` - HTTP mocking

**Documentation:**
- `mkdocs>=1.6.0` - Documentation generator
- `mkdocs-material>=9.5.0` - Material theme
- `mkdocstrings[python]>=0.26.0` - API docs

## Build System

Uses `hatchling` with `hatch-vcs` for version management:

```toml
[build-system]
requires = ["hatchling>=1.3.1", "hatch-vcs"]
build-backend = "hatchling.build"

[tool.hatch.version]
source = "vcs"
```

Version is automatically derived from git tags.

## See Also

- [Contributing Guide](contributing.md) - How to contribute
- [API Reference](../api/client.md) - API documentation
