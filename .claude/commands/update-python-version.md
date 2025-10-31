---
description: Update the minimum Python version requirement across the entire codebase
---

# Update Python Version Command

You are tasked with updating the minimum Python version requirement across the entire codebase.

## Input

The user will provide the new minimum Python version in the format "3.X" (e.g., "3.14", "3.15").

## Steps to Execute

### 1. Validate Input
- Ensure the provided version is in the correct format (e.g., "3.14")
- Extract the old version from `pyproject.toml` by reading the `requires-python` field

### 2. Search for All References
Search for all occurrences of the old Python version across the codebase. You must check at the very least:
- `pyproject.toml` - `requires-python` field
- `.readthedocs.yml` - Python version specification
- `.github/workflows/*.yaml` - Python version matrices and specifications
- `README.md` - Badge and requirements sections
- `docs/index.md` - Badge and requirements sections
- `docs/getting-started/installation.md` - Requirements section
- `docs/development/contributing.md` - Prerequisites section
- `docs/development/architecture.md` - Type hints references
- `CLAUDE.md` - Any version references

Use Grep to search for patterns like:
- The old version number (e.g., "3.13")
- Badge URLs containing the version (e.g., "python-3.13%2B")
- Version specifications in YAML files

### 3. Update All Files
Update ALL occurrences of the old version to the new version:

#### pyproject.toml
- Update `requires-python = ">=X.Y"` to the new version
- Update classifier `"Programming Language :: Python :: X.Y"` if present
- Note: This may trigger `uv.lock` regeneration

#### .readthedocs.yml
- Update `python: "X.Y"` to the new version

#### .github/workflows/*.yaml
- Update Python version matrices (e.g., `python-version: ["X.Y", ...]`)
- Add new version, potentially remove old unsupported versions

#### Documentation Files
- Update badges from `python-X.Y%2B` to `python-X.Z%2B`
- Update requirements text from "Python X.Y or higher" to "Python X.Z or higher"
- Update any other references (e.g., "(3.Y+)" to "(3.Z+)")

### 4. Regenerate Lock File
After updating `pyproject.toml`, regenerate the lock file:
```bash
uv sync --all-extras --group dev --group test --group docs
```

### 5. Run Quality Checks
Execute all quality checks to ensure nothing broke:

```bash
# Run linting and formatting
uv run pre-commit run --all-files

# Run type checking
uv run mypy src/

# Run tests
uv run pytest
```

### 6. Verify No Remaining References
After all updates, search again for the old version to ensure no references were missed:
```bash
grep -r "X.Y" . --exclude-dir=.git --exclude-dir=.venv --exclude="*.lock"
```

Review any remaining occurrences to determine if they need updating or are false positives.

### 7. Summary Report
Provide a summary of:
- All files that were updated
- The specific changes made in each file
- Test results and whether all checks passed
- Any remaining references to the old version (with explanation if they're false positives)

## Error Handling

If any step fails:
1. Report the failure clearly
2. Do not proceed to subsequent steps
3. Provide guidance on how to fix the issue

## Notes

- Always use exact string matching when replacing versions to avoid false positives
- Be careful with version strings that appear in git history or lock files
- Ensure all badge URLs are properly URL-encoded (use %2B for +)
- The command should be idempotent - running it multiple times should be safe
