---
status: open
severity: P1
found-in: v0.2.1
found-via: scaffold validation, 2026-05-21
---

# bug-003 — Scaffolded README points at `python -m <pkg>` but that fails

## Symptom

The scaffolded agent's own README says:

```bash
python -m code_reviewer "your task here"
```

But running it fails immediately:

```
'code_reviewer' is a package and cannot be directly executed
```

Workaround: `python -m code_reviewer.main "…"` — but that's not
what the README told the user.

## Reproduction

```bash
agentforge new test --template minimal --no-prompts
cd test && uv sync
python -m test "hi"   # fails
```

## Root cause

The package directory `src/<slug>/` ships `__init__.py` + `main.py`
but **no `__main__.py`** — so `python -m <pkg>` has no entry point.

## Fix

Add a `[project.scripts]` entry to every template's
`pyproject.toml`:

```toml
[project.scripts]
{{ project_slug }} = "{{ project_slug | replace('-', '_') }}.main:main"
```

And rewrite every template's README to use it:

```bash
uv sync
cp .env.example .env
uv run {{ project_slug }} "your task here"
```

This is more Pythonic than dropping a `__main__.py` shim, survives
reinstall cleanly, and matches the pattern `agentforge` itself uses
(the `agentforge` CLI ships as `[project.scripts] agentforge = …`).

## Verification

```bash
agentforge new test --template minimal --no-prompts
cd test && uv sync && uv run test "hi"
# Should reach Agent() construction without "cannot be directly executed".
```
