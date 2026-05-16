# Development Setup

Contributions are welcome! This guide covers development workflow, code style, testing, and how to build the docs.

## Prerequisites

- Python 3.14 or higher
- [uv](https://github.com/astral-sh/uv)
- Git

## Setup

```bash
git clone https://github.com/flz/iaqualink-py.git
cd iaqualink-py

# Install all dependencies including dev and test
uv sync --all-extras --all-groups
```

## Worktree Setup

When starting work in a new git worktree, run the setup script to wire hooks and verify the environment:

```bash
bash scripts/setup-worktree.sh
```

The script is idempotent: installs prek hooks for `pre-commit` and `pre-push` stages, checks that `uv` and `claude` are on `PATH`, and prints a checklist.

## Development Workflow

1. Create a branch: `git checkout -b feature/your-feature-name`
2. Edit code in `src/iaqualink/`
3. Add tests in `tests/` following existing structure
4. Run checks (see below)
5. Commit following [Conventional Commits](https://www.conventionalcommits.org/): `feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`
6. Push and open a pull request

## Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov-report=xml --cov=iaqualink

# Run a single file
uv run pytest tests/systems/iaqua/test_system.py

# Run a specific test
uv run pytest tests/systems/iaqua/test_system.py::TestIaquaSystem::test_update
```

Tests use `unittest.IsolatedAsyncioTestCase` and `respx` for HTTP mocking — no live network calls or real credentials needed. All new tests should use `TestBase` from `tests/base.py`.

## Code Quality

```bash
# Run all prek hooks (ruff, ruff-format, mypy)
uv run prek run --all-files

# Run with diff on failure
uv run prek run --show-diff-on-failure --color=always --all-files

# Ruff linting with auto-fix
uv run ruff check --fix .

# Ruff formatting
uv run ruff format .

# Type checking
uv run mypy src/
```

## Code Style

- Line length: 88 characters
- Type hints required on all public APIs
- Google-style docstrings for public APIs

```python
def example_function(param: str) -> int:
    """Brief description.

    Args:
        param: Description of parameter.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param is invalid.
    """
    return len(param)
```

## Logging

### Logger names

Each module uses a named child logger under the `iaqualink` root. The root logger is controlled by the CLI's `--debug` flag; children inherit it automatically.

| Module | Logger name |
|--------|-------------|
| `client.py` | `iaqualink.client` |
| `system.py` | `iaqualink.system` |
| `device.py` | `iaqualink.device` |
| `systems/iaqua/system.py`, `systems/iaqua/device.py` | `iaqualink.systems.iaqua` |
| `systems/exo/system.py`, `systems/exo/device.py` | `iaqualink.systems.exo` |
| `systems/i2d/system.py`, `systems/i2d/device.py` | `iaqualink.systems.i2d` |
| `cli/app.py` | `iaqualink.cli` |

When adding a new system, use `logging.getLogger("iaqualink.systems.<name>")` in both `system.py` and `device.py`.

### Sensitive data

Never log these values directly:

- Credentials: `password`, `api_key`
- Auth tokens: `authentication_token`, `id_token`, `refresh_token`, `client_id`
- Request secrets: HMAC `signature`, `sessionID`

When logging request parameters, use the redaction helpers from `client.py`:

```python
LOGGER.debug("-> %s %s %s", method, _redact_url(url), _redact_kwargs(kwargs))
```

`AqualinkAuthState.__repr__` masks token fields — logging an auth state object is safe.

Auth response bodies (login, refresh) contain raw tokens — never log them on success.

### Response body visibility

Parse methods log the full raw response body at `DEBUG` before any parsing logic:

```python
def _parse_foo_response(self, response: httpx.Response) -> None:
    data = response.json()
    LOGGER.debug("Foo body: %s", data)      # must be first
    ...
    LOGGER.debug("Foo parsed: serial=%s status=%s", self.serial, self.status.name)
```

### Log levels

| Level | Use for |
|-------|---------|
| `INFO` | Auth lifecycle: login, token refresh, reauth fallback |
| `DEBUG` | Normal flow: request/response details, parse results, device counts |
| `WARNING` | Unexpected but handled: unknown enum value, offline device, skipped update |
| `ERROR` / exception | Not used — raise exceptions instead |

## Building Docs

```bash
# Install docs dependencies
uv sync --group docs

# Serve locally with live reload
uv run mkdocs serve

# Build
uv run mkdocs build

# Build with strict mode (fail on warnings)
uv run mkdocs build --strict
```

## Pull Request Checklist

Before submitting:

- [ ] All tests pass (`uv run pytest`)
- [ ] Prek hooks pass (`uv run prek run --all-files`)
- [ ] Type checking passes (`uv run mypy src/`)
- [ ] Tests added or updated
- [ ] Documentation updated
- [ ] Commit messages follow Conventional Commits

PR description should include: what changed, why, any breaking changes, and how to test.

## Getting Help

- Open an issue for bugs
- Start a discussion for questions
- Check existing issues first

## License

By contributing, you agree that your contributions will be licensed under the BSD 3-Clause License.
