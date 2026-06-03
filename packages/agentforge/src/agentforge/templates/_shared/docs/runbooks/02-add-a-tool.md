# 02 — Add a tool

> **Goal:** make a new capability available to your agent's
> reasoning loop.
> **Time:** ~10 minutes.
> **Prereqs:** runbook 01 done.

## TL;DR

```python
from agentforge import tool

@tool
async def fetch_weather(*, city: str) -> str:
    """Return the current weather summary for `city`."""
    return await my_weather_api(city)

agent = Agent(model="...", tools=[fetch_weather])
```

## Step by step

1. **Decide tool surface** — what kwargs does the LLM pass? Each
   becomes a typed parameter on the function. Use Pydantic models
   only when the inputs are nested.
2. **Author the tool** with the `@tool` decorator. Type hints
   drive the JSON schema the LLM sees; do NOT hand-write a schema.
3. **Add a docstring** — the first line is what the LLM reads to
   decide when to call your tool. Keep it short and behaviour-
   focused: "Returns X given Y", not "This tool will...".
   **Name it with `[a-zA-Z0-9_-]` only** (1-64 chars) — that's the
   tool-name charset Bedrock, OpenAI, and Anthropic all enforce.
   A plain function name (`fetch_weather`) is already fine; avoid
   dots / colons / spaces in `@tool(name="...")` overrides.
4. **Pass the tool to `Agent(tools=[...])`** or list it under
   `agent.tools:` in `agentforge.yaml` so it's auto-resolved on
   `agentforge run`.
5. **Cover with a test** — instantiate via `FakeTool.fake(...)`
   for tests where the real call would be too slow / costly
   (see runbook 06).

## Variations

- **Class-based tool** — subclass `Tool` directly when you need
  per-instance state (DB pool, HTTP client). Pattern in
  `agentforge_core.contracts.tool`.
- **Destructive tools** — set `capabilities: ClassVar = frozenset
  ({"destructive"})` on the class. The `capability_check`
  guardrail (runbook 11) will deny it unless allowlisted.
- **Long-running tools** — return early with a status; let the
  next iteration check completion. Don't `await` for 30 seconds.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| LLM never calls the tool | docstring too vague | rewrite to be behaviour-focused: "Fetches X for Y" |
| `ValidationError` on tool call | type hints don't match LLM args | check the JSON schema with `tool.to_spec()` |
| Tool runs but observation lost | tool returns `None` | return a string (or a dict; the framework JSON-serialises) |
| Tool ran twice unexpectedly | LLM retried | check the previous observation surfaced clearly; vague observations cause retries |
| `ToolNameInvalidError` at first LLM call | tool name has a dot / colon / space, or is >64 chars | rename to `[a-zA-Z0-9_-]` only (the error suggests a legal form, e.g. `kb.search` → `kb_search`) |

## Related

- Runbook 06 — Test your agent (covers `FakeTool.fake`)
- Runbook 11 — Add safety guardrails (capability gating)
- Feature spec: `docs/features/feat-004-tools-system.md`

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
