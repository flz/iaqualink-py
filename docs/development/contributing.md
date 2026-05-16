# Contributing

Contributions are welcome! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.14 or higher
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Git

### Clone Repository

```bash
git clone https://github.com/flz/iaqualink-py.git
cd iaqualink-py
```

### Install Dependencies

Using uv (recommended):

```bash
# Install all dependencies including dev and test
uv sync --all-extras --dev
```

Using pip:

```bash
pip install -e ".[dev,test,docs]"
```

### Install Pre-commit Hooks

```bash
uv run pre-commit install
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

Edit the code in `src/iaqualink/`.

### 3. Write Tests

Add tests in `tests/` following the existing structure.

### 4. Run Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov-report=xml --cov=iaqualink

# Run specific test
uv run pytest tests/test_client.py::TestClassName::test_method
```

### 5. Check Code Quality

```bash
# Run all pre-commit hooks
uv run pre-commit run --all-files

# Or run individually:

# Linting with auto-fix
uv run ruff check --fix .

# Formatting
uv run ruff format .

# Type checking
uv run mypy src/
```

### 6. Commit Changes

```bash
git add .
git commit -m "feat: add new feature"
```

Follow [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `test:` - Test changes
- `refactor:` - Code refactoring
- `chore:` - Maintenance tasks

### 7. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub.

## Code Style

### Python Style

The project uses Ruff for linting and formatting:

- Line length: 80 characters
- Follow PEP 8
- Use type hints
- Write docstrings for public APIs

### Type Hints

All code must include type hints:

```python
def example_function(param: str) -> int:
    """Example function with type hints."""
    return len(param)
```

### Docstrings

Use Google-style docstrings:

```python
def example_function(param: str) -> int:
    """Brief description.

    Longer description if needed.

    Args:
        param: Description of parameter.

    Returns:
        Description of return value.

    Raises:
        ValueError: When param is invalid.
    """
    return len(param)
```

### Logging

#### Logger names

Each module uses a named child logger under the `iaqualink` root so callers can filter
output per subsystem. The root logger (`iaqualink`) is configured by the CLI's
`--debug` flag; all children inherit it automatically.

| Module | Logger name |
|--------|-------------|
| `client.py` | `iaqualink.client` |
| `system.py` | `iaqualink.system` |
| `device.py` | `iaqualink.device` |
| `systems/iaqua/system.py`, `systems/iaqua/device.py` | `iaqualink.systems.iaqua` |
| `systems/exo/system.py`, `systems/exo/device.py` | `iaqualink.systems.exo` |
| `systems/i2d/system.py`, `systems/i2d/device.py` | `iaqualink.systems.i2d` |
| `cli/app.py` | `iaqualink.cli` |

When adding a new system, use `logging.getLogger("iaqualink.systems.<name>")` in both
`system.py` and `device.py`.

#### Sensitive data

**Never** log the following values directly:

- Credentials: `password`, `_password`, `api_key`
- Auth tokens: `authentication_token`, `id_token`, `refresh_token`, `client_id`
- Request secrets: HMAC `signature`, `sessionID`

When logging request parameters, use the helpers in `client.py`:

```python
LOGGER.debug("-> %s %s %s", method, _redact_url(url), _redact_kwargs(kwargs))
```

`AqualinkAuthState.__repr__` already masks token fields — logging an auth state object is safe.

Auth **response** bodies (login, refresh) contain raw tokens — never log them on success.

#### Response body visibility

Parse methods log the full raw response body at `DEBUG` **before** any parsing logic, so even a
mid-parse crash shows exactly what the API returned:

```python
def _parse_foo_response(self, response: httpx.Response) -> None:
    data = response.json()
    LOGGER.debug("Foo body: %s", data)      # must be first — visible even if parse raises
    ...
    LOGGER.debug("Foo parsed: serial=%s status=%s", self.serial, self.status.name)
```

Device-state response bodies (home, devices, shadow, alldata) contain no auth tokens and are
safe to log in full. The body line provides API visibility for issue reports; the structured
summary at the end provides grep-friendly output.

#### Log levels

| Level | Use for |
|-------|---------|
| `INFO` | Auth lifecycle events: login, token refresh, reauth fallback |
| `DEBUG` | Normal flow: request/response details, parse results, device counts |
| `WARNING` | Unexpected but handled: unknown enum value, offline device, skipped update |
| `ERROR` / exception | Not used — raise exceptions instead |

Auth lifecycle events that warrant `INFO`:

```python
LOGGER.info("Authenticated: user=%s", self.username)
LOGGER.info("Auth token refreshed: user=%s", self.username)
LOGGER.info("Refresh token expired, re-authenticating: user=%s", self.username)
```

System status changes stay at `DEBUG` (noisy on frequent polling); unexpected status values
stay at `WARNING`.

## Testing

### Test Structure

Tests use `unittest.IsolatedAsyncioTestCase`:

```python
import unittest
from tests.base import TestBase

class TestMyFeature(TestBase):
    async def test_something(self):
        """Test something."""
        # Your test here
        pass
```

### Mocking HTTP Requests

Use `respx` for HTTP mocking:

```python
import respx
from httpx import Response

@respx.mock
async def test_api_call(self):
    respx.post("https://api.example.com/endpoint").mock(
        return_value=Response(200, json={"result": "success"})
    )

    # Test code that makes HTTP request
    result = await client.some_method()
    self.assertEqual(result, "success")
```

### Test Coverage

Maintain high test coverage:

```bash
# Generate coverage report
uv run pytest --cov-report=html --cov=iaqualink

# View report
open htmlcov/index.html
```

## Documentation

### Building Docs

```bash
# Install docs dependencies
uv sync --group docs

# Serve docs locally
uv run mkdocs serve

# Build docs
uv run mkdocs build
```

### Writing Docs

- Use Markdown
- Include code examples
- Keep it concise
- Test all examples

## Project Structure

```
iaqualink-py/
├── src/iaqualink/          # Source code
│   ├── client.py           # Main client
│   ├── system.py           # Base system
│   ├── device.py           # Base devices
│   ├── systems/
│   │   ├── iaqua/         # iAqua implementation
│   │   └── exo/           # eXO implementation
│   └── exception.py        # Exceptions
├── tests/                  # Test suite
│   ├── base.py            # Test base classes
│   ├── systems/
│   │   ├── iaqua/         # iAqua tests
│   │   └── exo/           # eXO tests
│   └── test_*.py          # Test files
├── docs/                   # Documentation
└── pyproject.toml         # Project config
```

## Adding New System Types

To add support for a new system type:

1. Create `src/iaqualink/systems/newsystem/`
2. Implement `NewSystem(AqualinkSystem)`
3. Set `NAME` class attribute
4. Implement device parsing methods
5. Create device classes
6. Add tests
7. Update documentation

See [Architecture](architecture.md) for details.

## Pull Request Guidelines

### Before Submitting

- [ ] All tests pass
- [ ] Code is formatted (ruff format)
- [ ] Code is linted (ruff check)
- [ ] Type checking passes (mypy)
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Commit messages follow conventions

### PR Description

Include:

- What changes were made
- Why the changes are needed
- Any breaking changes
- How to test the changes

### Review Process

1. Automated checks must pass
2. Code review by maintainer
3. Address feedback
4. Merge when approved

## Getting Help

- Open an issue for bugs
- Start a discussion for questions
- Check existing issues first

## Code of Conduct

Be respectful and constructive. This is an open source project maintained by volunteers.

## License

By contributing, you agree that your contributions will be licensed under the BSD 3-Clause License.
