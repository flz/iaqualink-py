# Contributing

Contributions are welcome! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.12 or higher
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
