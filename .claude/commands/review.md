---
description: Review the current branch vs master against .claude/review-criteria.md. Use before opening a PR.
---

# /review

1. Get the diff:

   ```bash
   git fetch -q origin master 2>/dev/null || true
   BASE=$(git merge-base HEAD origin/master 2>/dev/null || git rev-list --max-parents=0 HEAD)
   git diff --stat "$BASE"...HEAD
   git diff "$BASE"...HEAD -- src/ tests/ docs/reference/ docs/implementation/
   ```

   If empty, report "No changes vs master" and stop.

2. Read `.claude/review-criteria.md` and apply it to the diff. Skip sections
   whose trigger conditions don't apply (e.g. §1 when no protocol code
   changed). Do the §1 check inline — grep the reference doc for changed
   names; don't spawn a subagent for small diffs.

3. Output only the issues found, then one summary line:
   `ISSUES — address before merging` or `LGTM — ready for PR`.

Mechanical checks (lint, types, identifier scan) are covered by
`uv run prek run --all-files`; run that instead of reviewing them by hand.
