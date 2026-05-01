# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## General guidance (micro-caveman)

For conversational replies, not generated docs/comments, respond like smart caveman.
- Cut all filler, keep technical substance.
- Drop articles (a, an, the), filler (just, really, basically, actually).
- Drop pleasantries (sure, certainly, happy to).
- No hedging. Fragments fine. Short synonyms.
- Technical terms stay exact. Code blocks unchanged.
- Pattern: [thing] [action] [reason]. [next step].

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

# Run CLI tests
uv run pytest tests/test_cli.py

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
   - Uses `httpx-retries` for transport-level 429 retries with exponential backoff and `Retry-After`
   - Rebuilds and retries auth-bearing client-owned requests such as systems discovery through the shared reauth helper instead of replaying stale requests inside `send_request()`
   - Manages session tokens and credentials
   - Factory method `get_systems()` returns appropriate system subclasses

2. **AqualinkSystem** ([system.py](src/iaqualink/system.py)) - Base class for pool systems
   - Subclass registry pattern using `__init_subclass__` and `NAME` class attribute
   - `from_data()` factory method dispatches to correct subclass based on `device_type`
   - Two concrete implementations:
     - **IaquaSystem** ([systems/iaqua/system.py](src/iaqualink/systems/iaqua/system.py)) - For "iaqua" device_type
     - **ExoSystem** ([systems/exo/system.py](src/iaqualink/systems/exo/system.py)) - For "exo" device_type
   - Implements polling with rate limiting (MIN_SECS_TO_REFRESH per system: 5s iaqua, 50s exo)
   - Uses the shared reauth helper to retry iaqua and exo system requests once after refreshing auth on `AqualinkServiceUnauthorizedException`
   - Tracks online/offline status

3. **AqualinkDevice** ([device.py](src/iaqualink/device.py)) - Base class for devices
   - Device hierarchy: Sensor → BinarySensor → Switch → Light/Thermostat
   - System-specific implementations:
     - **IaquaDevice** ([systems/iaqua/device.py](src/iaqualink/systems/iaqua/device.py))
     - **ExoDevice** ([systems/exo/device.py](src/iaqualink/systems/exo/device.py))
   - Device types include: sensors, pumps, heaters, lights, thermostats, aux toggles

4. **CLI package** ([src/iaqualink/cli](src/iaqualink/cli)) - User-facing Typer command line client
   - Entry point is the packaged `iaqualink` script
   - Centralizes config loading from CLI options, environment variables, and `typer.get_app_dir("iaqualink") / "config.yaml"`
   - Persists session state in a JSON cookie jar at `typer.get_app_dir("iaqualink") / "session.json"` by default
   - Supports a global `--debug` flag that enables root logging at DEBUG before command execution
   - Exposes discovery commands such as `list-systems`, `list-devices`, and `status`
   - Exposes initial control commands such as `turn-on`, `turn-off`, and `set-temperature`

### Session Persistence

- `AqualinkClient` exposes typed auth snapshots through `AqualinkAuthState` and the `auth_state` getter/setter for CLI session reuse.
- Restored sessions skip the initial `login()` inside `__aenter__()`.
- The CLI performs one full login retry when a restored cookie jar is stale during systems discovery, then updates the jar on success.
- The CLI only restores a saved jar when the username in the jar matches the requested username.
- Cookie jars are written atomically via a temporary file and store tokens in plain text, so docs should keep the security tradeoff explicit.

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

- **Rate limiting:** Per-system `MIN_SECS_TO_REFRESH` class attribute (5s default, 50s exo)
- **API key:** Hardcoded AQUALINK_API_KEY for iAqua systems
- **Temperature ranges:** Different for Celsius/Fahrenheit, defined in device files

## Adding Support for New System Types

To add a new system type:
1. Create `systems/newsystem/` directory with `__init__.py`, `system.py`, `device.py`
2. Implement `NewSystem(AqualinkSystem)` with `NAME` class attribute
3. Override `MIN_SECS_TO_REFRESH` if the default (5s) is not appropriate
4. Implement device parsing in `_parse_*_response()` methods
5. Create corresponding device classes extending base device types
6. In `update()`, re-raise `AqualinkServiceThrottledException` before the broader `AqualinkServiceException` handler to prevent `online = None` on rate-limiting (see existing implementations in `iaqua/system.py` and `exo/system.py`)
7. Register the new system module import in `src/iaqualink/client.py` so `AqualinkSystem.from_data()` can discover the subclass at runtime
8. Add tests following existing patterns in `tests/systems/newsystem/`

## Quality Gates

Before finalizing any change, validate it against the API spec files in `spec/` if they exist and are relevant to the change:

1. Read the relevant section(s) of any spec files found under `spec/` for any endpoint, field, or behavior being added or modified.
2. Ensure URL paths, HTTP methods, request/response field names, and authentication flows match the spec exactly.
3. If the implementation diverges from the spec, document the reason explicitly in the code with a comment.

This step is mandatory alongside linting, type checking, and tests.

## Notes

- All API calls are asynchronous using httpx
- Client supports context manager protocol for automatic cleanup
- Exception hierarchy in [exception.py](src/iaqualink/exception.py) covers service errors, auth failures, offline systems
- Python 3.14+ required (uses modern type hints like `Self`, `type[T]`)
- Tests exclude private member access (SLF001) and f-string logging (G004) from ruff
