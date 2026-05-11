# 06 — Test your agent

> **Goal:** unit-test your agent without hitting a real LLM or
> network.
> **Time:** ~15 minutes.
> **Prereqs:** runbook 02 (you have at least one tool).

## TL;DR

```python
import pytest
from agentforge.testing import MockLLMClient, FakeTool, agent_factory

@pytest.mark.asyncio
async def test_population_lookup() -> None:
    llm = MockLLMClient.from_script([
        {"text": "Looking up.",
         "tool_calls": [{"name": "search", "args": {"q": "Spain"}}]},
        {"text": "47.5M", "stop_reason": "end_turn"},
    ])
    web = FakeTool.fake("search", lambda **kw: "47.5M people")
    agent = agent_factory(model=llm, tools=[web])
    result = await agent.run("How many in Spain?")
    assert "47.5M" in result.output
```

## Step by step

1. **Use `MockLLMClient.from_script(...)`** for tests that need
   to drive specific LLM responses. `deterministic("ok")` works
   when you only care that the loop completes.
2. **Stub tools with `FakeTool.fake(name, fn)`** — accepts a
   static value or a callable. Preserves the real tool's
   `name` so the LLM sees the same surface.
3. **Use `agent_factory(...)`** instead of raw `Agent(...)`. It
   bakes in safe defaults (in-memory store, no log filter
   mutation, low budget) so tests stay isolated.
4. **Assert on `result.output`** for the answer, and on
   `mock_llm.tool_calls_observed` for the LLM's tool-use
   sequence. Both are cheaper than parsing trace strings.
5. **Record once, replay forever.** For tests that exercise a
   real provider response, `record_llm(real, "cassette.jsonl")`
   captures it; subsequent runs use
   `MockLLMClient.from_recording(...)`.

## Variations

- **Property-based tests** — pair `agent_factory` with Hypothesis
  strategies for input fuzzing.
- **Golden sets** — `agentforge-testing` ships
  `GoldenSetRunner.from_jsonl(...)`; fixture lines hold
  `task` + `expected` (exact / contains / regex / any_of).
- **Snapshot rendering** — `assert_snapshot(text, path)` for
  scorecard / patch output. `UPDATE_SNAPSHOTS=1 pytest`
  re-records.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `MockLLMClient exhausted` | the agent made more LLM calls than scripted | extend the script or relax with `deterministic` |
| Test runs hit a real API | imported the real client by accident | wrap construction in `agent_factory(model=mock_llm)` |
| Stub-tool not invoked | name mismatch between FakeTool and what the script says the LLM called | both must use the same `name=` value |
| Flaky asyncio teardown warning | event-loop GC noise on macOS | already filtered in pyproject; safe to ignore |

## Related

- Runbook 02 — Add a tool
- Runbook 10 — Add evaluators
- Feature spec: `docs/features/feat-016-testing-framework.md`

<!-- agentforge:end-managed -->

<!-- agentforge:custom -->
<!-- agentforge:end-custom -->
