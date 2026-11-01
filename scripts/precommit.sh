#!/usr/bin/env bash
# pre-commit hook: flag third-party protocol identifiers that must not
# appear in repo-tracked files. Called with staged file paths as arguments.
set -euo pipefail

PATTERNS=(
    '\.java\b'
    '\.smali\b'
    '[A-Za-z][A-Za-z0-9]*/[A-Za-z][A-Za-z0-9]*/[A-Za-z][A-Za-z0-9]*\.java'
    'com\.zodiac\.'
    'com\.amazonaws\.'
    'networkmodule/'
    'iaqualinkandroid/'
    'infinity/'
    '\b(RetrofitClient|NetworkClient|SecurityUtils|ApiHelper|UserAuthenticationManager)\b'
)

FOUND=0

for file in "$@"; do
    [ -f "$file" ] || continue
    for pattern in "${PATTERNS[@]}"; do
        while IFS= read -r match; do
            echo "FAIL [$pattern] $match"
            FOUND=1
        done < <(grep -nE "$pattern" "$file" 2>/dev/null \
                 | sed "s|^|$file:|" || true)
    done
done

if [ "$FOUND" -ne 0 ]; then
    echo ""
    echo "Third-party protocol identifier(s) detected in staged files."
    echo "Remove them or add the file to the hook exclude list if intentional."
    exit 1
fi
