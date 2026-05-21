---
status: open
severity: P0
found-in: v0.2.1
found-via: scaffold validation, 2026-05-21
---

# bug-002 — Scaffolded `agentforge.yaml` missing required `agent.strategy`

## Symptom

After fixing [bug-001](./bug-001-scaffold-pyproject-missing-provider-extra.md)
(so the provider is installed), `Agent()` construction next fails
with:

```
agentforge_core.production.exceptions.ModuleError: No reasoning
strategy provided. …
```

## Reproduction

```bash
agentforge new test --template minimal --provider anthropic --no-prompts
cd test && uv sync && python -m test.main "hi"
```

## Root cause

`packages/agentforge/src/agentforge/templates/<all>/agentforge.yaml`
does not set `agent.strategy`. The framework has no default and
raises `ModuleError` on `Agent(...)` construction inside the user's
`main.py`.

## Fix

Add `strategy: "react"` to every template's `agentforge.yaml`
under `agent:`:

```yaml
agent:
  name: "{{ project_slug }}"
  model: "..."
  strategy: "react"
  ...
```

(Alternative: default `Agent._resolve_strategy` to `"react"` when
the configured field is absent. Doing it in YAML is more explicit
and lets users see + change the default. Pick the YAML fix.)

## Verification

Re-scaffold and confirm `Agent()` construction passes without
manual yaml edits — i.e., the only remaining hurdle for an
end-to-end run is providing a real API key in `.env`.
