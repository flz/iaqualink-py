# CLAUDE.md

Guidance for Claude Code in this repository. Read the linked docs only when
the task needs them.

## Confidentiality

Repo-tracked files must contain only wire-observable identifiers: hostnames,
URLs, HTTP header names, JSON field names, numeric constants, protocol
constants visible on the wire.

**NOT ALLOWED:** Java/Kotlin file paths, package names (`com.zodiac.*`,
`com.amazonaws.*`), class names, method names, variable names from any
external reference source. The private research tooling lives outside this
repo. `scripts/precommit.sh` scans for known patterns; it is not exhaustive.

## Project

Async Python (3.14+, httpx HTTP/2) library for Jandy iAqualink pool systems:
- **iAqua** — iaqualink.net API
- **eXO** — zodiac-io.com API (AWS IoT shadow)
- **i2d** — iQPump variable-speed pumps, r-api.iaqualink.net control API

Key patterns:
- `AqualinkSystem` uses `__init_subclass__` + `NAME` registry; `from_data()`
  dispatches by `device_type`.
- `refresh()` is a template method — `_refresh()` must set `self.status` on
  every path and must not catch `AqualinkServiceException` subclasses.
- Session persistence via `AqualinkAuthState`; CLI uses a cookie jar with
  atomic writes.
- Tests: plain pytest classes, `respx` for HTTP, `asyncio_mode = "auto"`.

## Where things are documented

| Topic | Doc |
|---|---|
| Setup, commands, logging rules | `docs/contributing/setup.md` |
| Architecture | `docs/contributing/architecture.md` |
| New system type (checklist) | `docs/contributing/new-system-type.md` |
| New base device type | `docs/contributing/new-device-type.md` |
| Auth, device list, HTTP config | `docs/reference/client.md` |
| Per-system protocol (source of truth) | `docs/reference/systems/<system>.md` |
| Accepted divergences | `docs/implementation/systems/<system>.md` → "Deltas vs Protocol Reference" |

**Protocol changes:** before changing an endpoint, field, or auth flow, grep
the relevant reference doc (don't read it end to end — `iaqua.md` is large)
and verify. If not covered, update the doc in the same commit. Confirm
before adding new divergences.

## Logging (quick rules)

- Logger: `logging.getLogger("iaqualink.systems.<name>")` for systems,
  `"iaqualink.<module>"` otherwise.
- Request logging: wrap with `_redact_url(url)` / `_redact_kwargs(kwargs)`.
- Parse methods: `LOGGER.debug("<Name> body: %s", data)` first after
  `data = response.json()`.
- **Never** log login/refresh response bodies (raw tokens).
- Auth events at INFO; everything else DEBUG or WARNING.

## Before declaring done

```bash
uv run prek run --all-files   # ruff, format, mypy, ty, identifier scan
uv run pytest -q
```

Run `/review` only when asked or before opening a PR — CI also reviews PRs.
