---
status: open
severity: P0
found-in: v0.2.1
found-via: scaffold validation, 2026-05-21
---

# bug-001 — `agentforge new` scaffold doesn't install the provider package

## Symptom

After `agentforge new my-agent --template <any> --provider anthropic`
and `uv sync`, attempting to run the agent fails with:

```
agentforge_core.production.exceptions.ModuleError: No LLM provider
registered for 'anthropic'. Install agentforge-anthropic …
```

## Reproduction

```bash
agentforge new code-reviewer --template code-reviewer --provider anthropic --no-prompts
cd code-reviewer && uv sync
python -m code_reviewer.main "hi"
```

## Root cause

`packages/agentforge/src/agentforge/templates/<all>/pyproject.toml`
declares only `agentforge-py` as a dep (plus a stale special-case
for `bedrock`). The `llm_provider` Copier variable is not used to
add the corresponding provider package.

Even if the template *did* install `agentforge-<provider>`, that
wouldn't pull the underlying SDK — the SDK lives behind a
`[<provider>]` extra on each provider sister package (lazy-import
pattern, per ADR-0004 + the `feedback_vendor_module_patterns`
memory).

## Fix

In every template's `pyproject.toml`:

```toml
dependencies = [
    "agentforge-py",
    "agentforge-{{ llm_provider }}[{{ llm_provider }}]",
    "python-dotenv>=1.0",
]
```

(removes the obsolete `bedrock` special-case; relies on the
`llm_provider` Copier choice matching one of `anthropic`,
`openai`, `bedrock` — same set the template already restricts to
via `copier.yml`.)

Bonus: chain `agentforge-py[<provider>]` extras to
`agentforge-<provider>[<sdk>]` in `packages/agentforge/pyproject.toml`
so `pip install "agentforge-py[anthropic]"` (no scaffold) also lands
the SDK end-to-end. Only applies to provider packages that *have*
an SDK extra — `agentforge-anthropic`, `agentforge-openai`, and
`agentforge-bedrock` do; `agentforge-ollama`, `agentforge-litellm`,
and `agentforge-voyage` ship the SDK as a hard dep so no extra is
needed:

```toml
anthropic = ["agentforge-anthropic[anthropic] ~= 0.2.1"]
openai    = ["agentforge-openai[openai] ~= 0.2.1"]
bedrock   = ["agentforge-bedrock[bedrock] ~= 0.2.1"]
# ollama, litellm, voyage: leave as-is (SDK is a hard dep).
```

## Verification

```bash
agentforge new test --template minimal --provider anthropic --no-prompts
cd test && uv sync
.venv/bin/pip list | grep -E "(agentforge-anthropic|^anthropic )"
# Both lines should appear; second confirms the underlying SDK is installed.
```
