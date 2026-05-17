---
description: Review library changes or device types against Home Assistant patterns. Flags compatibility issues and suggests improvements. Usage: /ha-review [diff|devices|<class_name>]
---

# /ha-review

Review the library against Home Assistant integration requirements.

## Modes

Run with no argument or one of:

| Argument | What it does |
|---|---|
| *(none)* | Reviews the current diff vs master for HA compatibility |
| `devices` | Reviews the full device hierarchy for HA compatibility and improvement opportunities |
| `<ClassName>` | Reviews a specific device class (e.g., `/ha-review IaquaThermostat`) |

## Steps

### 1. Gather context

**No argument / diff mode:**
```bash
git fetch origin master 2>/dev/null || true
BASE=$(git merge-base HEAD origin/master 2>/dev/null || git rev-list --max-parents=0 HEAD)
git diff "$BASE"...HEAD -- src/
```
Pass the diff to the `ha-reviewer` agent.

**`devices` mode:**
Read `src/iaqualink/device.py`, `src/iaqualink/systems/iaqua/device.py`, `src/iaqualink/systems/exo/device.py`, `src/iaqualink/systems/i2d/device.py`. Pass all four to the agent.

**Class name mode:**
Grep for the class across `src/iaqualink/` and read the file. Pass to the agent.

### 2. Invoke ha-reviewer

Pass the gathered context to the `ha-reviewer` subagent with the instruction:
- For diff mode: "Review this diff for HA entity compatibility issues."
- For devices mode: "Review the full device hierarchy for HA compatibility and suggest improvements."
- For class mode: "Review `<ClassName>` for HA entity compatibility and suggest improvements."

### 3. Output

Print the agent's report. Highlight any issues that would break existing HA integrations in red (prefix with `BREAKING:`).

## Notes

- Does not modify any files. Review only.
- To action a suggestion from this review, open a follow-up with the specific change in mind and implement it.
- HA entity base classes are fetched from `github.com/home-assistant/core` at review time — no local HA install required.
