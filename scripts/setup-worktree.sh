#!/usr/bin/env bash
# Idempotent worktree bootstrap. Run once after creating or entering a new worktree.
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"

echo "=== iAquaLink worktree setup ==="

# Check hard dependencies
command -v uv &>/dev/null || { echo "✗ uv not found — install from https://docs.astral.sh/uv/"; exit 1; }

# Install prek (pre-commit) hooks
uv run prek install --install-hooks --hook-type pre-commit
echo "✓ hooks installed (pre-commit stage)"

# Remove the stale pre-push hook left by older versions of this script
if [ -f "$(git rev-parse --git-common-dir)/hooks/pre-push" ] \
    && grep -q prek "$(git rev-parse --git-common-dir)/hooks/pre-push"; then
    uv run prek uninstall --hook-type pre-push >/dev/null 2>&1 || true
    echo "✓ removed obsolete pre-push hook"
fi

# Ensure hook scripts are executable
chmod +x scripts/precommit.sh
echo "✓ hook scripts marked executable"

echo ""
echo "Wired:"
echo "  pre-commit : trailing-ws  end-of-file  check-yaml  large-files"
echo "               ruff  ruff-format  mypy  uv-lock  check-identifiers"
echo ""
echo "Run tests: uv run pytest"
echo "Run linters: uv run prek run --all-files"
