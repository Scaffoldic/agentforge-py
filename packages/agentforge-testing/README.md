# agentforge-testing

Richer test helpers for AgentForge agents. Pip-installable
separately so the dependency doesn't land in production.

The lighter built-in surface — `MockLLMClient`, `FakeTool`,
`agent_factory`, conformance harnesses, `record_llm` /
`MockLLMClient.from_recording` — ships inside the `agentforge`
runtime package at `agentforge.testing`. Install **this** package
when you want, additionally:

- `GoldenSetRunner` — load JSONL fixtures, run an agent, compare
  output via structural diff with allow-listed wildcards.
- `assert_snapshot(actual, path)` — Approval-style snapshot file
  helper with `UPDATE_SNAPSHOTS=1` re-record.
- `analyze_recording(path)` — stats about a captured cassette
  (call count, token totals, distinct tool calls, per-step
  latency distribution).

```bash
uv add --dev agentforge-testing
```
