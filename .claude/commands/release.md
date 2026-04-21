---
description: Propose and create the next release tag (final or release candidate)
---

# Release Command

Create the next versioned git tag. The GitHub Actions release workflow fires automatically on any `v*` tag push, handling GitHub Release creation and PyPI publishing — including pre-releases, which are published to the real PyPI (not Test PyPI) with pre-release status.

## Input

The user may optionally pass `rc` to create a release candidate instead of a final release.

## Steps to Execute

### 1. Validate Branch and Sync Tags

Run the following commands:

```bash
git rev-parse --abbrev-ref HEAD
git fetch --tags
```

- If HEAD is detached or the branch is not `master`, **stop and tell the user**. Tagging from a non-master branch is almost certainly a mistake. Do not proceed unless the user explicitly confirms they know what they're doing and want to tag this commit anyway.
- The `git fetch --tags` ensures the local tag list matches the remote before any version analysis — a developer may have pushed a tag that isn't local yet.

### 2. Determine the Latest Tag

Run:
```bash
git tag --sort=-version:refname | head -20
```

Identify:
- **Latest final release tag** — highest `vX.Y.Z` tag without a pre-release suffix (e.g. `v0.6.0`)
- **Latest RC tag for the next version** — if any `vX.Y.Z-rc.N` tag exists beyond the latest final release, note the highest N

### 3. Analyze Commits Since Last Final Release

Run:
```bash
git log <latest-final-tag>..HEAD --format="%s%n%b%n---"
```

This captures both the subject line and the full message body, which is necessary because `BREAKING CHANGE:` may appear in the commit footer rather than the subject (per the Conventional Commits spec).

Classify across the full output of each commit using these rules:

| Indicator | Bump |
|-----------|------|
| Subject contains `!` after the type (e.g. `feat!:`, `fix!:`), **or** any line in the body/footer contains `BREAKING CHANGE:` | **major** |
| Subject starts with `feat` (and no breaking change detected) | **minor** |
| Only `fix`, `build`, `chore`, `ci`, `docs`, `refactor`, `test`, `perf`, `style` | **patch** |

Apply the highest-priority bump found.

If there are **no commits** since the last final release, stop and tell the user there is nothing to release.

### 4. Propose the Next Version

Compute the proposed tag from the latest final release:

- **major bump**: increment major, reset minor and patch to 0 → `vX+1.0.0`
- **minor bump**: increment minor, reset patch to 0 → `vX.Y+1.0`
- **patch bump**: increment patch → `vX.Y.Z+1`

**If creating a release candidate (`rc` argument passed):**

Check whether an RC tag for this proposed version already exists (e.g. `vX.Y.Z-rc.1`). If yes, increment N. Otherwise start at `-rc.1`.

Final proposed tag examples:
- Final release: `v0.7.0`
- First RC: `v0.7.0-rc.1`
- Subsequent RC: `v0.7.0-rc.2`

### 5. Present a Summary and Ask for Confirmation

Display a clear summary to the user:

```
Latest final release : v0.6.0
Commits since release: 51
Bump type            : minor  (new features detected)
Proposed tag         : v0.7.0  [or v0.7.0-rc.1 for RC]

Notable commits:
  feat(exo): add ExoFilterPump controllable switch
  feat(exo): add ExoErrorSensor for diagnostic error fields
  feat: add token refresh with fallback to full re-login on 401
  fix: cleanup retry logic for 401/429
  fix: update iAqua session URL to v2 r-api endpoint
  ... (only feat/fix/breaking — skip build/chore/ci/docs bumps)

Note: RC tags are published to the real PyPI (pre-release status).
      pip install iaqualink won't pick them up; pip install --pre will.

Shall I create and push tag <proposed-tag>? (yes/no)
```

Wait for explicit confirmation before proceeding. If the user suggests a different version, use that instead.

### 6. Create and Push the Tag

Once confirmed, create an **annotated** tag (stores tagger identity, timestamp, and message — preferred for release tags and required for `git describe` to work correctly):

```bash
git tag -a <proposed-tag> -m "Release <proposed-tag>"
git push origin <proposed-tag>
```

### 7. Report Outcome

Tell the user:
- The tag that was created and pushed
- That the GitHub Actions release workflow has been triggered
- The GitHub Actions URL to monitor progress: `https://github.com/flz/iaqualink-py/actions`
- For RCs: this publishes to the real PyPI as a pre-release (`pip install --pre iaqualink` to install)
- For final releases: this publishes to PyPI as a stable release

## Error Handling

- If `git push` fails (e.g. tag already exists remotely), report the error clearly and do not retry automatically.
- If the working tree has uncommitted changes, warn the user but do not block — a tag points to a commit, not the working tree.
- If no conventional commit prefixes are found, default to a **patch** bump and note the assumption.
