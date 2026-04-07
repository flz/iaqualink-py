# Documentation Setup

This project uses MkDocs with the Material theme for documentation.

## Setup

Install documentation dependencies:

```bash
uv sync --group docs
```

## Local Development

Serve documentation locally with live reload:

```bash
uv run mkdocs serve
```

Then visit http://127.0.0.1:8000

## Building

Build the documentation:

```bash
uv run mkdocs build
```

Build with strict mode (fail on warnings):

```bash
uv run mkdocs build --strict
```

## Deployment

### GitHub Pages

Documentation is automatically deployed to GitHub Pages when changes are pushed to the `master` or `main` branch.

The workflow is defined in `.github/workflows/docs.yml`.

**Setup GitHub Pages:**

1. Go to your repository settings
2. Navigate to Pages
3. Set Source to "GitHub Actions"
4. The documentation will be available at: https://flz.github.io/iaqualink-py/

### ReadTheDocs

Documentation can also be hosted on ReadTheDocs.

**Setup ReadTheDocs:**

1. Go to https://readthedocs.org/
2. Import your project
3. The configuration is in `.readthedocs.yml`
4. Documentation will be available at: https://iaqualink-py.readthedocs.io/

## Documentation Structure

```
docs/
├── index.md                    # Home page
├── getting-started/
│   ├── installation.md        # Installation guide
│   ├── quickstart.md          # Quick start guide
│   └── authentication.md      # Authentication details
├── guide/
│   ├── systems.md             # Systems guide
│   ├── devices.md             # Devices guide
│   └── examples.md            # Code examples
├── api/
│   ├── client.md              # Client API reference
│   ├── system.md              # System API reference
│   ├── device.md              # Device API reference
│   ├── iaqua.md               # iAqua systems
│   ├── exo.md                 # eXO systems
│   └── exceptions.md          # Exceptions reference
└── development/
    ├── contributing.md        # Contributing guide
    └── architecture.md        # Architecture documentation
```

## Features

- **Material Theme** - Modern, responsive design
- **Code Highlighting** - Syntax highlighting for Python code
- **Search** - Full-text search functionality
- **API Documentation** - Auto-generated from docstrings using mkdocstrings
- **Dark Mode** - Automatic light/dark theme switching
- **Mobile Friendly** - Responsive design for mobile devices

## Configuration

The documentation is configured in `mkdocs.yml`:

- Site metadata (name, description, URLs)
- Theme settings (Material theme with dark mode)
- Navigation structure
- Plugins (search, mkdocstrings)
- Markdown extensions

## Writing Documentation

### Markdown Files

Documentation pages are written in Markdown with support for:

- Standard Markdown syntax
- Code blocks with syntax highlighting
- Admonitions (notes, warnings, etc.)
- Tables
- Task lists

### API Documentation

API documentation is automatically generated from docstrings using mkdocstrings:

```markdown
::: iaqualink.client.AqualinkClient
```

This will include the class documentation, methods, and properties.

### Code Examples

Use fenced code blocks with language specification:

```markdown
\`\`\`python
from iaqualink import AqualinkClient

async with AqualinkClient(username, password) as client:
    systems = await client.get_systems()
\`\`\`
```

### Admonitions

Use admonitions for notes, warnings, and tips:

```markdown
!!! note "Optional Title"
    This is a note.

!!! warning
    This is a warning.

!!! tip
    This is a tip.
```

## Dependencies

Documentation dependencies are in `pyproject.toml` under `[dependency-groups.docs]`:

- `mkdocs` - Static site generator
- `mkdocs-material` - Material theme
- `mkdocstrings[python]` - API documentation from docstrings
