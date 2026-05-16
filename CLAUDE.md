# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Confidentiality

Repo-tracked files must contain only wire-observable identifiers: hostnames, URLs, HTTP header names, JSON field names, numeric constants, protocol constants visible on the wire.

**ALLOWED:** hostnames, URLs, HTTP header names, JSON wire field names, numeric constants, protocol constants observable at the wire level.

**NOT ALLOWED:** Java/Kotlin file paths, package names (`com.zodiac.*`, `com.amazonaws.*`), class names, method names, variable names from any external reference source.

The private tooling that researches protocol behavior and produces architecture docs lives outside this repo.

---

## Project Overview

Async Python library for Jandy iAqualink pool control systems. Three system types:
- **iAqua** — iaqualink.net API
- **eXO** — zodiac-io.com API (AWS IoT shadow)
- **i2d** — iQPump variable-speed pumps, r-api.iaqualink.net control API

## Development Commands

See `docs/contributing/setup.md` for setup, testing, linting, and docs commands.

Worktree setup: `bash scripts/setup-worktree.sh` (idempotent; installs prek hooks, checks PATH).

## Architecture

See `docs/contributing/architecture.md` for class hierarchy, auth patterns, session management, and data flow.

Key patterns:
- `AqualinkSystem` uses `__init_subclass__` + `NAME` subclass registry; `from_data()` dispatches by `device_type`
- `refresh()` is a template method — concrete systems implement `_refresh()`, must set `self.status` before returning
- Session persistence via `AqualinkAuthState`; CLI uses cookie jar with atomic writes
- Tests: `unittest.IsolatedAsyncioTestCase`, `TestBase` in `tests/base.py`, `respx` for HTTP mocking

## API Reference

See `docs/reference/` for per-system wire-level protocol specs (source of truth for endpoints, fields, enums).

## Adding Support for New System Types

1. Create `systems/newsystem/` with `__init__.py`, `system.py`, `device.py`
2. Implement `NewSystem(AqualinkSystem)` with `NAME` class attribute
3. Implement `async def _refresh(self) -> None` — called by base `refresh()` template method
4. Inside `_refresh()`, set `self.status` before returning. Do **not** catch `AqualinkServiceException` subclasses — `refresh()` handles those
5. Implement device parsing in `_parse_*_response()` methods
6. Create device classes extending base device types
7. Register module import in `src/iaqualink/client.py` so `AqualinkSystem.from_data()` discovers the subclass
8. Add tests following existing patterns in `tests/systems/newsystem/`
9. Update documentation — all of the following in the same PR:
   - `README.md` — add to Multi-System Support list
   - `docs/index.md` — add to Features list
   - `mkdocs.yml` — add nav entries under Getting Started, API Reference, Protocol Reference, Implementation Notes
   - `docs/getting-started/newsystem.md` — API overview, status table, device inventory
   - `docs/implementation/newsystem.md` — status lifecycle, design decisions, deltas vs reference
   - `docs/api/newsystem.md` — `:::` autodoc directives for system + device classes
   - `docs/reference/newsystem.md` — wire-level protocol documentation

## Adding New Base Device Types

When adding a new direct subclass of `AqualinkDevice` to `device.py`, also add a corresponding entry to `_DEVICE_GROUPS` in `src/iaqualink/cli/app.py`. Devices without a matching group silently fall through to the "Other" bucket.

| Class | CLI Group | Notes |
|---|---|---|
| `AqualinkThermostat` | Thermostats | |
| `AqualinkLight` | Lights | |
| `AqualinkSwitch` | Switches | |
| `AqualinkPump` | Pumps | |
| `AqualinkNumber` | Numbers | |
| `AqualinkSensor` | Sensors | `AqualinkBinarySensor` extends `AqualinkSensor` and is covered by this entry |

Subclasses must appear before their superclass in `_DEVICE_GROUPS` (e.g. `AqualinkLight` before `AqualinkSwitch`). Only add a row for direct subclasses of `AqualinkDevice`; intermediate classes like `AqualinkBinarySensor` are automatically covered by their parent's entry.

## Protocol Reference

`docs/reference/<system>.md` is the source of truth for protocol behavior in this repo:

- `docs/reference/client.md` — auth flow, login/refresh shapes, device list, HTTP client config
- `docs/reference/iaqua.md` — iQ20 pool controller: session endpoint, commands, response field shapes, enum wire values
- `docs/reference/exo.md` — EXO/SWC chlorinator: shadow REST endpoints, full state field reference, write shapes
- `docs/reference/i2d.md` — iQPump: control endpoint, alldata fields, write format, offline signals

**Before changing any endpoint, field, or auth flow:** read the relevant reference doc and verify the change matches. If not covered, update the doc in the same commit.

**Divergences from reference behavior** are documented in the "Deltas vs current implementation" section of each reference doc and the corresponding `docs/implementation/<system>.md`. Confirm intentional divergences before adding new ones.

## Logging Guidelines

See [`docs/contributing/setup.md` — Logging section](docs/contributing/setup.md#logging) for the full reference.

Quick rules:
- New module logger: `logging.getLogger("iaqualink.systems.<name>")` for system modules; `"iaqualink.<module>"` otherwise.
- Request logging: always wrap with `_redact_url(url)` and `_redact_kwargs(kwargs)` from `client.py`.
- Parse methods: `LOGGER.debug("<Name> body: %s", data)` must be the first line after `data = response.json()`.
- **Never** log auth response bodies (login/refresh) — they contain raw tokens.
- Auth events (`login`, token refresh, reauth fallback) log at INFO; everything else at DEBUG or WARNING.

## Review Checklist

Before declaring any diff done, self-apply `.claude/review-criteria.md`.

Mandatory pre-declare commands:

```bash
uv run prek run --show-diff-on-failure --color=always --all-files
uv run pytest
uv run mypy src/
```

## Notes

- All API calls async via httpx (HTTP/2)
- Context manager protocol for automatic cleanup
- Exception hierarchy in `exception.py`: service errors, auth failures, offline systems
- Python 3.14+ required (`Self`, `type[T]`)
- Tests exclude SLF001 (private member access) and G004 (f-string logging) from ruff
