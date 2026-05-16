#!/usr/bin/env bash
# pre-push hook: run Claude AI review against .claude/review-criteria.md.
# Skippable with: git push --no-verify
set -euo pipefail

if ! command -v claude &>/dev/null; then
    echo "⚠  claude not on PATH — skipping AI review."
    echo "   Install Claude Code or use --no-verify to suppress this message."
    exit 0
fi

ROOT=$(git rev-parse --show-toplevel)
CRITERIA="$ROOT/.claude/review-criteria.md"

if [ ! -f "$CRITERIA" ]; then
    echo "⚠  .claude/review-criteria.md not found — skipping AI review."
    exit 0
fi

BASE=$(git merge-base HEAD origin/master 2>/dev/null \
    || git rev-list --max-parents=0 HEAD 2>/dev/null \
    || true)

if [ -z "$BASE" ]; then
    echo "⚠  Could not determine merge base — skipping AI review."
    exit 0
fi

DIFF=$(git diff "$BASE"...HEAD --diff-filter=ACMR 2>/dev/null | head -c 60000 || true)

if [ -z "$DIFF" ]; then
    echo "No source changes to review."
    exit 0
fi

echo "Running Claude review (.claude/review-criteria.md)…"

TMPFILE=$(mktemp)
trap 'rm -f "$TMPFILE"' EXIT

{
    printf 'Apply every section of the following review rubric to the diff below.\n'
    printf 'Report ONLY issues found. Format each issue as:\n'
    printf '  §<section_number> <file>:<line> — <one-line description>\n'
    printf 'If all sections are clean, output exactly: LGTM\n\n'
    printf '=== RUBRIC ===\n'
    cat "$CRITERIA"
    printf '\n=== DIFF ===\n'
    printf '%s\n' "$DIFF"
} > "$TMPFILE"

RESULT=$(claude --print "$(cat "$TMPFILE")" 2>&1) || true

echo "$RESULT"

if echo "$RESULT" | grep -qE "^§0 "; then
    echo ""
    echo "BLOCKED: §0 Confidentiality issue detected. Fix before pushing."
    exit 1
fi

exit 0
