#!/usr/bin/env bash
# Idempotent worktree bootstrap. Run once after creating or entering a new worktree.
set -euo pipefail

ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"

echo "=== iAquaLink worktree setup ==="

# Install prek (pre-commit) hooks for both stages
uv run prek install --install-hooks --hook-type pre-commit --hook-type pre-push
echo "✓ hooks installed (pre-commit + pre-push stages)"

# Ensure hook scripts are executable
chmod +x scripts/precommit.sh scripts/claude-review-hook.sh
echo "✓ hook scripts marked executable"

# Check for claude CLI (non-fatal)
if command -v claude &>/dev/null; then
    echo "✓ claude on PATH"
else
    echo "⚠  claude not on PATH — pre-push AI review will be skipped"
    echo "   Install Claude Code to enable: https://claude.ai/code"
fi

echo ""
echo "Wired:"
echo "  pre-commit : trailing-ws  end-of-file  check-yaml  large-files"
echo "               ruff  ruff-format  mypy  uv-lock  check-identifiers"
echo "  pre-push   : claude-review (skip with --no-verify)"
echo ""
echo "Run tests: uv run pytest"
echo "Run linters: uv run prek run --all-files"
