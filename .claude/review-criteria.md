# Review Criteria

Judgement-only rubric for diffs against `master`. Mechanical checks are
enforced by prek/CI and must not be re-reviewed: ruff (imports, `print`,
logging format, blocking calls in async), ruff-format, mypy, ty, and the
confidentiality identifier scan (`scripts/precommit.sh`).

Report issues as `§<N> <file>:<line> — <one-line description>`; clean
sections are omitted. If nothing to flag: `LGTM`.

## §1 Protocol correctness

Only if the diff touches `src/iaqualink/client.py`, `reauth.py`,
`src/iaqualink/const.py`, `src/iaqualink/shared/`, or `systems/<system>/`.
Grep `docs/reference/systems/<system>.md` (or `docs/reference/client.md`) for
each changed URL, method, header, query param, JSON field, or enum value —
don't read the doc end to end.
- Must match the reference, or appear in the "Deltas vs Protocol Reference"
  table in `docs/implementation/systems/<system>.md`.
- New protocol behavior not in the reference → the doc must be updated in
  the same PR.

## §2 Confidentiality (beyond the identifier scan)

Only wire-observable identifiers in tracked files (see `CLAUDE.md`). Flag
names that look lifted from a decompiled client (class/method/variable
names) even if they don't match the scan's patterns.

## §3 Async and error handling

- Missing `await`; `get_event_loop()`; `asyncio.run()` in a coroutine;
  fire-and-forget tasks without a stored reference; shared state mutated
  across coroutines without a lock (see `_refresh_lock`).
- `AqualinkServiceThrottledException` re-raised before the broader
  `AqualinkServiceException` handler.
- `AqualinkServiceUnauthorizedException` not swallowed; request code that
  can 401 goes through `_send_with_reauth_retry()` / `send_with_reauth_retry()`.
- `_refresh()` sets `self.status` on every path.
- No raw response bodies, tokens, or passwords in exception messages or logs.

## §4 Design

- Subclasses register via `NAME` + `__init_subclass__`; no `device_type`
  branches in base classes.
- New direct `AqualinkDevice` subclass → entry in `_DEVICE_GROUPS`
  (`src/iaqualink/cli/app.py`).
- No extra HTTP calls in `update()` beyond what the reference specifies; no
  background tasks or polling in library code; reuse the shared httpx client.
- User-controlled values go through httpx `params`, not string concatenation.
- No `Any` in public API without a comment.

## §5 Tests

- Every new state-mutating or network-calling public method has a test
  (`respx` for HTTP).
- New system types: factories in `tests/systems/<system>/factories.py` plus
  `test_system.py` and `test_device.py`.
