# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an asynchronous Python library for interacting with Jandy iAqualink pool control systems. The library supports two system types:
- **iAqua** systems - Uses the iaqualink.net API
- **eXO** systems - Uses the zodiac-io.com API (added in recent version)

## Development Commands

### Setup
```bash
# Install dependencies with uv
uv sync --all-extras --dev
```

### Testing
```bash
# Run all tests
uv run pytest

# Run tests with coverage
uv run pytest --cov-report=xml --cov=iaqualink

# Run a single test file
uv run pytest tests/test_client.py

# Run a specific test
uv run pytest tests/test_client.py::TestClassName::test_method_name
```

### Linting and Type Checking
```bash
# Run all pre-commit hooks (ruff, ruff-format, mypy)
uv run pre-commit run --all-files

# Run with diff on failure
uv run pre-commit run --show-diff-on-failure --color=always --all-files

# Ruff linting with auto-fix
uv run ruff check --fix .

# Ruff formatting
uv run ruff format .

# Type checking with mypy (excludes tests/)
uv run mypy src/
```

### Documentation
```bash
# Install documentation dependencies
uv sync --group docs

# Serve documentation locally (live reload)
uv run mkdocs serve

# Build documentation
uv run mkdocs build

# Build with strict mode (fail on warnings)
uv run mkdocs build --strict
```

## Architecture

### Core Class Hierarchy

The library follows a plugin-style architecture with base classes and system-specific implementations:

1. **AqualinkClient** ([client.py](src/iaqualink/client.py)) - Entry point for authentication and system discovery
   - Handles login/authentication for both API types
   - Uses httpx with HTTP/2 support
   - Manages session tokens and credentials
   - Factory method `get_systems()` returns appropriate system subclasses

2. **AqualinkSystem** ([system.py](src/iaqualink/system.py)) - Base class for pool systems
   - Subclass registry pattern using `__init_subclass__` and `NAME` class attribute
   - `from_data()` factory method dispatches to correct subclass based on `device_type`
   - Two concrete implementations:
     - **IaquaSystem** ([systems/iaqua/system.py](src/iaqualink/systems/iaqua/system.py)) - For "iaqua" device_type
     - **ExoSystem** ([systems/exo/system.py](src/iaqualink/systems/exo/system.py)) - For "exo" device_type
   - Implements polling with rate limiting (MIN_SECS_TO_REFRESH = 5 seconds)
   - Tracks online/offline status

3. **AqualinkDevice** ([device.py](src/iaqualink/device.py)) - Base class for devices
   - Device hierarchy: Sensor → BinarySensor → Switch → Light/Thermostat
   - System-specific implementations:
     - **IaquaDevice** ([systems/iaqua/device.py](src/iaqualink/systems/iaqua/device.py))
     - **ExoDevice** ([systems/exo/device.py](src/iaqualink/systems/exo/device.py))
   - Device types include: sensors, pumps, heaters, lights, thermostats, aux toggles

### API Differences

**iAqua Systems:**
- Authentication returns `session_id` and `authentication_token`
- Uses query parameters for authentication
- Two API calls for updates: "get_home" and "get_devices"
- Commands sent as session requests with specific command names

**eXO Systems:**
- Authentication returns JWT `IdToken` in `userPoolOAuth` field
- Uses Authorization header with IdToken
- Single shadow state API (AWS IoT-style)
- State updates via desired/reported state pattern
- Token refresh handled automatically on 401 responses

### Test Structure

Tests use `unittest.IsolatedAsyncioTestCase` with a custom base class:
- **TestBase** ([tests/base.py](tests/base.py)) - Base test class with AqualinkClient setup
- Uses `respx` library for HTTP mocking
- System-specific tests under `tests/systems/iaqua/` and `tests/systems/exo/`
- Abstract base tests in `base_test_system.py` and `base_test_device.py`

### Key Constants

- **Rate limiting:** System updates throttled to 5 second intervals ([const.py](src/iaqualink/const.py))
- **API key:** Hardcoded AQUALINK_API_KEY for iAqua systems
- **Temperature ranges:** Different for Celsius/Fahrenheit, defined in device files

## Adding Support for New System Types

To add a new system type:
1. Create `systems/newsystem/` directory with `__init__.py`, `system.py`, `device.py`
2. Implement `NewSystem(AqualinkSystem)` with `NAME` class attribute
3. Implement device parsing in `_parse_*_response()` methods
4. Create corresponding device classes extending base device types
5. Add tests following existing patterns in `tests/systems/newsystem/`

## Notes

- All API calls are asynchronous using httpx
- Client supports context manager protocol for automatic cleanup
- Exception hierarchy in [exception.py](src/iaqualink/exception.py) covers service errors, auth failures, offline systems
- Python 3.12+ required (uses modern type hints like `Self`, `type[T]`)
- Tests exclude private member access (SLF001) and f-string logging (G004) from ruff
