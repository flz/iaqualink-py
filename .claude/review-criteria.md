# Review Criteria

Use this rubric when reviewing any diff against `master`. Each item is independently checkable. Stop and flag before declaring the review done.

---

## 0. Confidentiality (check first — hard blocker)

Repo-tracked files must contain only wire-observable identifiers.

**ALLOWED** in repo: hostnames, URLs, HTTP header names, JSON wire field names, numeric constants, named protocol constants whose names are observable at the wire level.

**NOT ALLOWED**: Java/Kotlin file paths, package names (`com.zodiac.*`, `com.amazonaws.*`, etc.), class names, method names, variable names from any external reference source.

Action: grep the diff for `.java`, `com.zodiac`, `com.amazonaws`, `infinity/`, `networkmodule/`, `iaqualinkandroid/`, `RetrofitClient`, `NetworkClient`, `SecurityUtils`, `ApiHelper`. Flag any hit that is not inside a meta-rule statement. Ensure only the wire-level manifestation of any concept (field name, URL path, header value) appears in the repo.

---

## 1. Protocol Correctness

- Every URL path, HTTP method, query parameter, and JSON field name must match `docs/getting-started/<system>.md` for the system being changed.
- If the diff diverges from the architecture doc, a comment in the code must explain why.
- Check auth header format per system: iQ20 session uses bare `IdToken`; shadow endpoints vary — verify against the architecture doc.
- New constants (URLs, paths, header names) must trace to the architecture doc, not be invented.

---

## 2. Async Correctness

This is an `asyncio`-based library. Flag any of the following:

- Blocking I/O in a coroutine: `open()`, `time.sleep()`, `requests.*`, `subprocess.*`, synchronous `socket.*`, or any call that blocks the event loop.
- Missing `await` on a coroutine call.
- `asyncio.get_event_loop()` — use `asyncio.get_running_loop()` instead.
- `asyncio.run()` called inside a coroutine.
- Shared mutable state accessed from multiple coroutines without a lock (see `_refresh_lock` pattern in `client.py`).
- Fire-and-forget tasks created without storing a reference (task GC).

---

## 3. Error Handling

- `AqualinkServiceThrottledException` must be re-raised before the broader `AqualinkServiceException` handler in any `update()` method. Swallowing throttle errors sets `online = None` incorrectly.
- `AqualinkServiceUnauthorizedException` triggers the reauth retry path in `reauth.py` — do not catch it silently in request code.
- All new request code that can receive a 401 must go through `_send_with_reauth_retry()` (system-level) or `send_with_reauth_retry()` (client-level).
- Exception messages must not include raw HTTP response bodies (may contain credentials).

---

## 4. Type Annotations

- All new public and private functions/methods must have complete annotations (parameters + return type).
- Use `Self` (from `typing`) for `__aenter__` / factory methods that return the same class.
- `TYPE_CHECKING` guard for imports used only in annotations.
- No `Any` in public API surface unless genuinely unavoidable, and commented.
- `mypy` must pass cleanly: `uv run mypy src/` with no new errors.

---

## 5. Code Quality and Best Practices

- No commented-out code.
- No `print()` — use `LOGGER = logging.getLogger("iaqualink")`.
- No f-string logging: `LOGGER.debug("x=%s", x)` not `LOGGER.debug(f"x={x}")`.
- Constants in module scope, not inline magic strings or numbers (exception: trivial `""` / `0` / `1` states).
- New device/system subclasses must register via the `NAME` + `__init_subclass__` pattern — no manual dict edits.
- `from_data()` dispatch must use the subclass registry; do not add `if device_type == "..."` branches to base classes.
- No `import *`.

---

## 6. Test Coverage

- Every new public method that mutates state or makes a network call must have at least one test.
- Tests use `respx` for HTTP mocking and `unittest.IsolatedAsyncioTestCase`.
- New system types must have tests under `tests/systems/<system>/test_system.py` and `test_device.py` following the abstract base pattern in `tests/base_test_system.py` and `tests/base_test_device.py`.
- Fixtures (mock responses) belong in `tests/` alongside the test file that uses them.
- Tests must not import from `src/iaqualink` using private names (ruff SLF001 is suppressed in tests, but avoid it anyway).
- `uv run pytest` must pass with no new failures or warnings promoted to errors.

---

## 7. Performance

- No redundant HTTP calls: `update()` must not make more requests than the architecture doc specifies for that system.
- No polling loops inside library code — the library is called by the consumer; it must not start background tasks.
- Connection reuse: new code must not create `httpx.AsyncClient` instances per-request; use the shared client from `AqualinkClient._get_httpx_client()`.

---

## 8. Security

- No credentials, tokens, or API keys hardcoded in source or tests (use fixtures/constants).
- No logging of token values, passwords, or raw request bodies at any log level.
- URL construction must not allow injection: use `httpx` params dict, not f-string concatenation for user-controlled values.
- Cookie jar writes use atomic temp-file pattern (see CLI session persistence).

---

## 9. Pre-commit Compliance

Run before declaring done:

```bash
uv run pre-commit run --show-diff-on-failure --color=always --all-files
uv run pytest
uv run mypy src/
```

All three must be clean. Trailing whitespace, missing newlines, and lock-file drift are caught by pre-commit — fix them, do not suppress hooks.

---

## 10. Spec Validation

If the diff touches or adds any endpoint, field, or auth flow: read the relevant section of `docs/getting-started/<system>.md` and verify the implementation matches. If the doc does not yet cover the change, update the doc as part of the same commit. Do not ship protocol changes without doc coverage.
