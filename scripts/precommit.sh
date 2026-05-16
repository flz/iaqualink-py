#!/usr/bin/env bash
# pre-commit hook: flag generic decompiler artifact identifiers.
# Called with staged file paths as arguments.
# Specific class/package name checking is handled by the Claude AI review
# (see .claude/review-criteria.md §0).
set -euo pipefail

PATTERNS=(
    '\.java\b'
    '\.smali\b'
    '[A-Za-z][A-Za-z0-9]*/[A-Za-z][A-Za-z0-9]*/[A-Za-z][A-Za-z0-9]*\.java'
)

FOUND=0

for file in "$@"; do
    [ -f "$file" ] || continue
    for pattern in "${PATTERNS[@]}"; do
        while IFS= read -r match; do
            echo "FAIL [$pattern] $match"
            FOUND=1
        done < <(grep -nP "$pattern" "$file" 2>/dev/null \
                 | sed "s|^|$file:|" || true)
    done
done

if [ "$FOUND" -ne 0 ]; then
    echo ""
    echo "Decompiler artifact identifier(s) detected in staged files."
    echo "Remove them or add the file to the hook exclude list if intentional."
    exit 1
fi
