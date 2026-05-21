---
status: open
severity: P2
found-in: v0.2.1
found-via: scaffold validation, 2026-05-21
---

# bug-005 — Error messages refer to `agentforge[<extra>]` instead of `agentforge-py[<extra>]`

## Symptom

Two locations in the framework refer to `agentforge[<extra>]`
install commands. But the PyPI distribution is `agentforge-py`, not
`agentforge` — the latter import name is only the Python module.
Users who copy-paste the install command get:

```
ERROR: Could not find a version that satisfies the requirement agentforge[react]
ERROR: No matching distribution found for agentforge[react]
```

## Reproduction

```bash
pip install "agentforge[react]"   # 404
```

## Root cause

The import package is `agentforge` but the PyPI distribution is
`agentforge-py` (per `packages/agentforge/pyproject.toml` line 16:
`name = "agentforge-py"`). Two strings drift across the codebase:

- `packages/agentforge/src/agentforge/__init__.py:14` —
  module docstring: *"… or use the `agentforge[<extra>]` install
  (per ADR-0003)."*
- `packages/agentforge/src/agentforge/agent.py:243` — error
  message in `_resolve_strategy` (overlaps with [bug-004](./bug-004-stale-feat-002-error-message.md)).

## Fix

Replace `agentforge[<extra>]` with `agentforge-py[<extra>]` in both
locations.

## Verification

```bash
grep -rn 'agentforge\[' packages/agentforge*/src/
# Should return no results — every install hint should read
# agentforge-py[...].
```
