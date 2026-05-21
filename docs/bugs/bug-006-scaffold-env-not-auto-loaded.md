---
status: open
severity: P1
found-in: v0.2.1
found-via: scaffold validation, 2026-05-21
---

# bug-006 — Scaffolded `.env` is never loaded by the agent's entry point

## Symptom

The scaffold ships `.env.example` and the agent README tells the
user to:

```bash
cp .env.example .env
# add ANTHROPIC_API_KEY=… to .env
uv run <slug> "task"
```

But the resulting run fails because the entry-point `main.py`
doesn't load `.env` — the Anthropic SDK never sees the key:

```
TypeError: Could not resolve authentication method. Expected one of
api_key, auth_token, or credentials to be set …
```

## Reproduction

```bash
agentforge new test --template minimal --no-prompts
cd test && uv sync
cp .env.example .env
# write ANTHROPIC_API_KEY=… to .env
uv run test "hi"      # fails on missing key, despite .env being filled
```

## Root cause

`packages/agentforge/src/agentforge/templates/*/src/.../main.py`
does not call `load_dotenv()`. The `.env` file is created by the
template, copied by the user, then ignored by the agent at runtime.

## Fix

In every template's `main.py.tmpl`:

```python
from __future__ import annotations

import asyncio
import sys

from dotenv import load_dotenv

from agentforge import Agent

load_dotenv()
```

`python-dotenv` is added to template dependencies as part of the
[bug-001](./bug-001-scaffold-pyproject-missing-provider-extra.md)
fix, so this needs no extra dependency wiring.

(Alternative: `Agent()` itself could call `load_dotenv()` on
construction. Doing it in user code is more explicit and visible —
and matches what every Python developer expects when they see a
`.env` file in a scaffold.)

## Verification

After `agentforge new` + `cp .env.example .env` (with the key
filled in), `uv run <slug> "hi"` succeeds end-to-end against the
provider.
