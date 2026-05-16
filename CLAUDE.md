# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Confidentiality

Repo-tracked files must contain only wire-observable identifiers: hostnames, URLs, HTTP header names, JSON field names, numeric constants, protocol constants visible on the wire.

**ALLOWED:** hostnames, URLs, HTTP header names, JSON wire field names, numeric constants, protocol constants observable at the wire level.

**NOT ALLOWED:** Java/Kotlin file paths, package names (`com.zodiac.*`, `com.amazonaws.*`), class names, method names, variable names from any external reference source.

The private tooling that researches protocol behavior and produces architecture docs lives outside this repo.

---

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
# Run all prek hooks (ruff, ruff-format, mypy)
uv run prek run --all-files

# Run with diff on failure
uv run prek run --show-diff-on-failure --color=always --all-files

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

### Worktree Setup

When starting work in a new git worktree, run the setup script to wire hooks and verify the environment:

```bash
bash scripts/setup-worktree.sh
```

The script (idempotent):
- Installs pre-commit hooks for both `pre-commit` and `pre-push` stages
- Checks that `uv` and `claude` are on `PATH`
- Prints a checklist of what is wired

## Architecture

### Core Class Hierarchy

The library follows a plugin-style architecture with base classes and system-specific implementations:

1. **AqualinkClient** ([client.py](src/iaqualink/client.py)) - Entry point for authentication and system discovery
   - Handles login/authentication for both API types
   - Uses httpx with HTTP/2 support
   - Rebuilds and retries auth-bearing client-owned requests such as systems discovery through the shared reauth helper instead of replaying stale requests inside `send_request()`
   - Manages session tokens and credentials
   - Factory method `get_systems()` returns appropriate system subclasses

2. **AqualinkSystem** ([system.py](src/iaqualink/system.py)) - Base class for pool systems
   - Subclass registry pattern using `__init_subclass__` and `NAME` class attribute
   - `from_data()` factory method dispatches to correct subclass based on `device_type`
   - Two concrete implementations:
     - **IaquaSystem** ([systems/iaqua/system.py](src/iaqualink/systems/iaqua/system.py)) - For "iaqua" device_type
     - **ExoSystem** ([systems/exo/system.py](src/iaqualink/systems/exo/system.py)) - For "exo" device_type
   - Uses the shared reauth helper to retry iaqua and exo system requests once after refreshing auth on `AqualinkServiceUnauthorizedException`
   - Tracks online/offline status

3. **AqualinkDevice** ([device.py](src/iaqualink/device.py)) - Base class for devices
   - Device hierarchy: Sensor → BinarySensor → Switch → Light/Thermostat
   - System-specific implementations:
     - **IaquaDevice** ([systems/iaqua/device.py](src/iaqualink/systems/iaqua/device.py))
     - **ExoDevice** ([systems/exo/device.py](src/iaqualink/systems/exo/device.py))
   - Device types include: sensors, pumps, heaters, lights, thermostats, aux toggles

4. **Request signing** ([util.py](src/iaqualink/util.py)) - HMAC-SHA1 utility
   - `sign(parts, secret)` joins `parts` with `,` and returns lowercase hex HMAC-SHA1
   - Used by `AqualinkClient` for system discovery; designed to cover all three signature variants from the spec (device list — implemented; shadow and commands — future)

5. **CLI package** ([src/iaqualink/cli](src/iaqualink/cli)) - User-facing Typer command line client
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

**System Discovery (all system types):**
- Uses `https://r-api.iaqualink.net/v2/devices.json`
- HMAC-SHA1 signature over `"{user_id},{timestamp}"` with `AQUALINK_API_SIGNING_KEY`
- Auth via `Authorization: Bearer {IdToken}` header and `api_key` header

**iAqua Systems:**
- Authentication returns `session_id` and `authentication_token`
- Device commands use session tokens as query parameters
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
- **TestBase** ([tests/base.py](tests/base.py)) — base test class with `AqualinkClient` and `respx` mock transport pre-wired
- Uses `respx` for HTTP mocking — no live network calls; no real credentials needed
- System-specific tests under `tests/systems/iaqua/` and `tests/systems/exo/`
- Abstract base tests in `base_test_system.py` and `base_test_device.py` — new system types must subclass these
- Mock HTTP response fixtures (JSON dicts / response bodies) live alongside the test file that uses them in the same `tests/systems/<system>/` directory
- Run all tests: `uv run pytest`
- Run one file: `uv run pytest tests/systems/iaqua/test_system.py`
- Run one case: `uv run pytest tests/systems/iaqua/test_system.py::TestIaquaSystem::test_update`

### Key Constants

- **API key:** Hardcoded AQUALINK_API_KEY for iAqua systems
- **Temperature ranges:** Different for Celsius/Fahrenheit, defined in device files

## Adding Support for New System Types

To add a new system type:
1. Create `systems/newsystem/` directory with `__init__.py`, `system.py`, `device.py`
2. Implement `NewSystem(AqualinkSystem)` with `NAME` class attribute
3. Implement `async def _refresh(self) -> None` — the extension point called by the base `refresh()` template method
4. Inside `_refresh()`, set `self.status` before returning (any non-`IN_PROGRESS` value satisfies the post-condition check). Do **not** catch `AqualinkServiceException` or its subclasses — `refresh()` handles those automatically
5. Implement device parsing in `_parse_*_response()` methods
6. Create corresponding device classes extending base device types
7. Register the new system module import in `src/iaqualink/client.py` so `AqualinkSystem.from_data()` can discover the subclass at runtime
8. Add tests following existing patterns in `tests/systems/newsystem/`

## Adding New Base Device Types

When adding a new direct subclass of `AqualinkDevice` to `device.py`, you **must** also add a corresponding entry to `_DEVICE_GROUPS` in `src/iaqualink/cli/app.py`. Devices without a matching group silently fall through to the "Other" bucket in the CLI output. The current base types and their CLI group order are:

| Class | CLI Group | Notes |
|---|---|---|
| `AqualinkThermostat` | Thermostats | |
| `AqualinkLight` | Lights | |
| `AqualinkSwitch` | Switches | |
| `AqualinkPump` | Pumps | |
| `AqualinkNumber` | Numbers | |
| `AqualinkSensor` | Sensors | `AqualinkBinarySensor` extends `AqualinkSensor` and is covered by this entry |

Subclasses must appear before their superclass in `_DEVICE_GROUPS` (e.g. `AqualinkLight` before `AqualinkSwitch`). Only add a new row for direct subclasses of `AqualinkDevice`; intermediate classes like `AqualinkBinarySensor` are automatically covered by their parent's entry.

## Protocol Reference

`docs/reference/<system>.md` is the source of truth for protocol behavior in this repo:

- `docs/reference/client.md` — auth flow, login/refresh request+response shapes, device list, HTTP client config
- `docs/reference/iaqua.md` — iQ20 pool controller: session endpoint, all commands, response field shapes, enum wire values
- `docs/reference/exo.md` — EXO/SWC chlorinator: shadow REST endpoints, full state field reference, write shapes

**Before changing any endpoint, field, or auth flow:** read the relevant section of the architecture doc and verify the change matches. If the doc does not cover the change, update the doc in the same commit.

**Divergences from reference behavior** are documented in the "Deltas vs current implementation" section of each architecture doc. Before adding new divergences, confirm they are intentional and add them to the appropriate doc.

## Review Checklist

Before declaring any diff done, self-apply `.claude/review-criteria.md`. That file contains the full rubric used by the GitHub PR reviewer. Running it locally closes the gap between local iteration and PR feedback.

The mandatory pre-declare commands:

```bash
uv run pre-commit run --show-diff-on-failure --color=always --all-files
uv run pytest
uv run mypy src/
```

## Notes

- All API calls are asynchronous using httpx
- Client supports context manager protocol for automatic cleanup
- Exception hierarchy in [exception.py](src/iaqualink/exception.py) covers service errors, auth failures, offline systems
- Python 3.14+ required (uses modern type hints like `Self`, `type[T]`)
- Tests exclude private member access (SLF001) and f-string logging (G004) from ruff
