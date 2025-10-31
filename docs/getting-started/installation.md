# Installation

## Using pip

The easiest way to install iaqualink-py is using pip:

```bash
pip install iaqualink
```

## Using uv

If you're using [uv](https://github.com/astral-sh/uv), you can install it with:

```bash
uv add iaqualink
```

## From Source

To install from source for development:

```bash
# Clone the repository
git clone https://github.com/flz/iaqualink-py.git
cd iaqualink-py

# Install with all dependencies
uv sync --all-extras --dev
```

## Requirements

- Python 3.13 or higher
- httpx with HTTP/2 support

All required dependencies will be installed automatically.

## Verifying Installation

You can verify the installation by running:

```python
import iaqualink
print(iaqualink.__version__)
```

## Next Steps

- [Quick Start](quickstart.md) - Get started with basic usage
- [Authentication](authentication.md) - Learn about authentication
