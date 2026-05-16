---
description: Run the full .claude/review-criteria.md rubric against the current diff vs master. Use before opening a PR.
---

# /review

Run the review rubric against the current branch.

## Steps

### 1. Get the diff

```bash
git fetch origin master 2>/dev/null || true
BASE=$(git merge-base HEAD origin/master 2>/dev/null \
    || git rev-list --max-parents=0 HEAD)
git diff "$BASE"...HEAD
```

If the diff is empty, report "No changes vs master" and stop.

### 2. §0 — Confidentiality (hard blocker — check first)

Grep the diff for the patterns listed in `.claude/review-criteria.md` §0:

```bash
git diff "$BASE"...HEAD | grep -nP \
    '\.java\b|com\.zodiac\.|com\.amazonaws\.|networkmodule/|iaqualinkandroid/|RetrofitClient\b|NetworkClient\b|SecurityUtils\b|ApiHelper\b|UserAuthenticationManager\b'
```

Any hit is a hard blocker. Report each match as `§0 <file>:<line> — <match>`. Do not proceed with the rest of the review if §0 fails.

### 3. §1 — Protocol Correctness

Invoke the `architecture-auditor` subagent with the diff. Pass the full diff text as context. Report its output verbatim under `§1`.

### 4. §2–§10 — Remaining rubric sections

Work through each remaining section of `.claude/review-criteria.md` in order (§2 Async Correctness through §10 Spec Validation). For each section:

- Read the diff against the criteria.
- Report issues as: `§<N> <file>:<line> — <one-line description>`
- If the section is clean: `§<N> LGTM`

### 5. Summary

After all sections: print a one-line summary.
- If any blocker: `BLOCKED — fix §<N> before opening PR`
- If issues but no blockers: `ISSUES — address before merging`
- If all clean: `LGTM — ready for PR`

## Notes

- This command mirrors what the GitHub `claude-code-review.yml` bot runs on every PR. Running it locally closes the feedback loop before push.
- Use `git push --no-verify` to skip the automated pre-push hook if you need to push work-in-progress.
- To review a specific commit range: run `/review` then manually adjust the `BASE` ref if needed.
