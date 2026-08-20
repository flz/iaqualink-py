# Architecture

Internal architecture of iaqualink-py.

## Overview

The library follows a plugin-style architecture with base classes and system-specific implementations. This design allows supporting multiple API types (iAqua, eXO, i2d) through a unified interface.

## Core Components

### 1. AqualinkClient

**Location:** `src/iaqualink/client.py`

Entry point for all interactions with the iAqualink API.

**Responsibilities:**
- Authentication (all system types)
- HTTP client management (httpx with HTTP/2)
- System discovery
- Session management

**Key features:**
- Context manager support for automatic cleanup
- Automatic system type detection via subclass registry
- Token/session management with reauth on 401

### 2. AqualinkSystem

**Location:** `src/iaqualink/system.py`

Base class for pool systems using a registry pattern.

**Responsibilities:**
- Device management
- State polling (template method `refresh()`)
- Online/offline status tracking

**Design Pattern: Subclass Registry**

```python
class AqualinkSystem:
    _subclasses: dict[str, type[Self]] = {}

    def __init_subclass__(cls, **kwargs):
        if hasattr(cls, 'NAME'):
            cls._subclasses[cls.NAME] = cls

    @classmethod
    def from_data(cls, aqualink, data):
        device_type = data.get('device_type')
        subclass = cls._subclasses.get(device_type)
        return subclass(aqualink, data)
```

**Implementations:**
- **IaquaSystem** — `NAME = "iaqua"`
- **ExoSystem** — `NAME = "exo"`
- **I2dSystem** — `NAME = "i2d"`

### 3. AqualinkDevice

**Location:** `src/iaqualink/device.py`

Base class for all devices.

**Hierarchy (flat — all are direct subclasses of `AqualinkDevice`):**

```
AqualinkDevice (ABC)
├── AqualinkSensor        — read-only sensor; maps to HA SensorEntity
├── AqualinkBinarySensor  — read-only on/off sensor; maps to HA BinarySensorEntity
├── AqualinkSwitch        — controllable on/off; maps to HA SwitchEntity
├── AqualinkButton        — stateless action trigger; maps to HA ButtonEntity
├── AqualinkLight         — controllable light; maps to HA LightEntity
├── AqualinkClimate       — temperature control; maps to HA ClimateEntity
├── AqualinkNumber        — writable numeric setting; maps to HA NumberEntity
├── AqualinkSelect        — single-choice picker; maps to HA SelectEntity
└── AqualinkFan           — fan/pump control; maps to HA FanEntity
```

Each subclass uses `@abstractmethod` for required overrides and `raise NotImplementedError`
stubs for optional overrides that concrete classes implement only when the feature is supported.
Template methods (e.g. `set_temperature`, `set_value`) validate arguments and delegate to
private `_set_*` methods that concrete classes implement.

### 4. Utilities

**Location:** `src/iaqualink/utils/crypto.py`

Shared HMAC-SHA1 helpers.

**`sign(parts, secret)`**

Joins `parts` with `,` and returns a lowercase hex HMAC-SHA1 digest:

```python
sign(["user_id", "timestamp"], api_signing_key)           # device list (v2) — implemented
sign(["serial", "user_id"], api_signing_key)              # device shadow — future
sign(["serial", "user_id", "timestamp"], api_signing_key) # commands/writes — future
```

Raises `ValueError` if `parts` is empty.

## System Implementations

### iAqua Systems

**Location:** `src/iaqualink/systems/iaqua/`

**API Characteristics:**
- Endpoint: `p-api.iaqualink.net`
- Auth: Session tokens (`session_id`, `authentication_token`)
- Two API calls per update: `get_home` + `get_devices` (+ `get_onetouch` if supported)
- Commands: GET requests to session endpoint with `command` query parameter

See [Implementation Notes: iAqua](../implementation/systems/iaqua.md) for status lifecycle and deltas.

### eXO Systems

**Location:** `src/iaqualink/systems/exo/`

**API Characteristics:**
- Endpoint: `prod.zodiac-io.com`
- Auth: JWT `IdToken` (Bearer)
- Single shadow state API (AWS IoT style)
- State updates via desired/reported pattern
- Automatic token refresh on 401

See [Implementation Notes: eXO](../implementation/systems/exo.md) for status lifecycle and deltas.

### i2d Systems

**Location:** `src/iaqualink/systems/i2d/`

**API Characteristics:**
- Endpoint: `r-api.iaqualink.net`
- Auth: Bearer `IdToken` + `api_key` header
- Single POST endpoint for all operations (`/alldata/read` + `/{key}/write`)
- `motordata` sub-object flattened into top-level data dict at parse time

See [Implementation Notes: i2d](../implementation/systems/i2d.md) for status lifecycle and deltas.

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
      → Fetch device list from r-api.iaqualink.net/v2/devices.json
      → HMAC-SHA1 signed request (user_id + timestamp)
      → For each system:
          → Extract device_type
          → AqualinkSystem.from_data()
          → Registry lookup by device_type
          → Instantiate correct subclass
      → Return dict[serial, system]
```

### Device Refresh Flow

```
system.refresh()                        ← public API; template method
      → status = IN_PROGRESS
      → await system._refresh()         ← system-specific implementation
          → fetch from API
          → parse response (sets status)
          → update device states
      → assert status != IN_PROGRESS
```

### Command Flow

```
device.turn_on()
      → Build command (system-specific)
      → Send to API via system
      → Return (state updates on next poll)
```

## Session Persistence

`AqualinkClient` exposes typed auth snapshots through `AqualinkAuthState` and the `auth_state` getter/setter for CLI session reuse.

- Restored sessions skip the initial `login()` inside `__aenter__()`
- The CLI performs one full login retry when a restored cookie jar is stale during systems discovery
- Cookie jars are written atomically via a temporary file and store tokens in plain text

## Type System

The library uses modern Python type hints (3.14+):

```python
from typing import Self, Any

class AqualinkSystem:
    def __init__(self, aqualink: AqualinkClient, data: dict[str, Any]): ...

    @classmethod
    def from_data(cls, aqualink: AqualinkClient, data: dict[str, Any]) -> Self: ...
```

## Testing Architecture

**Pattern:** plain pytest classes with per-test `_make_*()` helper functions; no shared base class.

**Structure:**
```
tests/
├── conftest.py               # Shared helpers: dotstar, resp_200, async_noop
├── test_client.py
├── utils/
│   ├── test_crypto.py
│   └── test_redact.py
├── conformance/
│   ├── conftest.py           # Aggregates factories, parametrized fixtures
│   ├── fixtures.py           # Fixture dataclasses (SwitchFixture, etc.)
│   └── test_*.py             # Conformance tests per device/system type
└── systems/
    ├── iaqua/
    │   ├── factories.py      # Factory functions for conformance fixtures
    │   ├── fixtures/         # JSON HTTP mock responses
    │   └── test_*.py         # Wire-protocol and parsing tests
    ├── exo/
    │   └── ...               # Same structure as iaqua/
    └── i2d/
        └── ...               # Same structure as iaqua/
```

Mock HTTP fixtures live alongside the test file in the same `tests/systems/<system>/` directory.

## System Status Lifecycle

`AqualinkSystem.refresh()` is a template method that owns the full status lifecycle. Concrete systems implement `_refresh()` and follow this contract:

### What `refresh()` does automatically

| Event | Status set |
|-------|-----------|
| Called | `IN_PROGRESS` |
| `AqualinkServiceThrottledException` raised by `_refresh()` | `UNKNOWN` |
| `AqualinkServiceException` raised | `DISCONNECTED` |
| `_refresh()` returns normally | *(set by `_refresh()` before returning)* |

### `_refresh()` contract

**On normal return** — set `self.status` to a resolved value before returning. If `_refresh()` returns without changing status, `refresh()` logs a warning.

**`AqualinkServiceThrottledException` / `AqualinkServiceException`** — do *not* catch these inside `_refresh()`. Let them propagate to `refresh()`, which maps them to `UNKNOWN` / `DISCONNECTED`.

## Error Handling

**Exception hierarchy:**

```
AqualinkException
└── AqualinkServiceException
    ├── AqualinkLoginException
    ├── AqualinkServiceUnauthorizedException
    ├── AqualinkServiceThrottledException
    └── AqualinkSystemOfflineException
```

**Location:** `src/iaqualink/exception.py`

## Dependencies

**Runtime:**
- `httpx[http2]` — HTTP client with HTTP/2

**Development:**
- `ruff` — Linting and formatting
- `mypy` — Type checking
- `pytest` — Testing
- `respx` — HTTP mocking

**Documentation:**
- `mkdocs` + `mkdocs-material` — Documentation generator
- `mkdocstrings[python]` — API docs from docstrings

## Build System

Uses `hatchling` with `hatch-vcs` for version management from git tags:

```toml
[build-system]
requires = ["hatchling>=1.3.1", "hatch-vcs"]
build-backend = "hatchling.build"

[tool.hatch.version]
source = "vcs"
```

## See Also

- [New System Type](new-system-type.md) — Step-by-step guide to adding a new system
- [New Device Type](new-device-type.md) — Adding a new base device class
- [API Reference](../api/client.md)
