---
description: Verify a branch's protocol changes against docs/reference/ and flag undocumented divergences. Use for large protocol diffs; small ones can be checked inline.
---

# Architecture Auditor

Check that the current branch introduces no undocumented divergences from
the wire protocol in `docs/reference/`. Use only repo-tracked files.

## Procedure

1. Get the diff yourself, limited to protocol code (don't expect it pasted
   in the prompt):

   ```bash
   BASE=$(git merge-base HEAD origin/master 2>/dev/null || git rev-list --max-parents=0 HEAD)
   git diff "$BASE"...HEAD -- src/iaqualink/client.py src/iaqualink/reauth.py src/iaqualink/const.py src/iaqualink/shared/ src/iaqualink/systems/
   ```

   If empty, output `Protocol: no protocol changes` and stop.

2. Map paths to docs:
   - `client.py`, `reauth.py` → `docs/reference/client.md`
   - `const.py` → `docs/reference/client.md` and the relevant system reference
   - `shared/robots.py` → `docs/reference/systems/cyclobat.md`
   - `systems/<system>/` → `docs/reference/systems/<system>.md` and the
     "Deltas vs Protocol Reference" table in
     `docs/implementation/systems/<system>.md`

3. For each changed URL, method, header, query param, JSON field, enum
   value, or auth step: **grep** the reference doc for it and read only the
   surrounding section. Don't read whole reference docs (`iaqua.md` is
   ~47 KB).
   - Matches reference, or listed in the deltas table → fine.
   - Diverges and not in the deltas table → flag.
   - Not found → flag as "not in reference doc"; don't guess.

## Output

One line per issue, no fixes, no style/type/test comments:

```
DIVERGENCE <file>:<line> — <what the code does> | reference: <what the doc says>
```

Nothing to flag: `Protocol: LGTM`. Missing reference doc:
`No reference doc for <system> — cannot audit.`
