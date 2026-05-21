---
status: open
severity: P2
found-in: v0.2.1
found-via: scaffold validation, 2026-05-21
---

# bug-004 — Error message says "when feat-002 ships" but feat-002 has shipped

## Symptom

When `Agent()` is constructed without a strategy, the error reads:

```
No reasoning strategy provided. feat-001 ships only the
ReasoningStrategy ABC; install agentforge[react] (when feat-002
ships) or pass a custom ReasoningStrategy instance via
Agent(strategy=...).
```

The `(when feat-002 ships)` parenthetical is wrong — feat-002 has
shipped. ReActLoop is registered by default. Mentioning it as
"future" is misleading at best, and at worst suggests the framework
isn't actually production-ready to a first-time user reading the
trace.

## Reproduction

Construct `Agent()` without `strategy=` and without a `strategy:`
field in `agentforge.yaml`.

## Root cause

`packages/agentforge/src/agentforge/agent.py:241-246` — stale
string from feat-001 era, never updated when feat-002 shipped.

## Fix

```python
raise ModuleError(
    "No reasoning strategy provided. Set `agent.strategy: \"react\"` "
    "in agentforge.yaml, pass `strategy=\"react\"` to `Agent(...)`, "
    "or pass a custom `ReasoningStrategy` instance via "
    "`Agent(strategy=...)`."
)
```

## Verification

```bash
grep -rn "feat-00[0-9]" packages/*/src/
# No user-facing string should reference feat-NNN as a future event.
# (Doc references to feat-NNN.md specs are fine — they're spec links,
# not "when feat-NNN ships" statements.)
```
