---
status: fixed in 0.3.0
severity: P2
found-in: 0.2.4
found-via: dogfooding (README demo gif)
---

# bug-023 — `agentforge run --replay` drops the configured strategy, so the replay happy path always fails

## Symptom

Replaying any recorded run fails before it starts:

```
$ agentforge run --replay 01KV76FZTJ2SZ9EKV5R5Z10DAD --path agentforge.yaml "…"
agentforge run: failed to construct agent: No reasoning strategy provided.
Set `agent.strategy: "react"` in agentforge.yaml, pass `strategy="react"`
to `Agent(...)`, or pass a custom `ReasoningStrategy` instance via
`Agent(strategy=...)`.
```

Every real recording was driven by a strategy (`react`, `plan-execute`,
…), so `--replay` is unusable end-to-end: it exits 1 for any recording
that isn't a degenerate no-strategy run.

## Reproduction

```bash
# config has agent.strategy + modules.memory: sqlite
agentforge run --record "Summarise the Agile Manifesto in three bullets." --path agentforge.yaml
# → prints a run_id, persists the run to the sqlite store
agentforge run --replay <that-run-id> --path agentforge.yaml "…"
# → "failed to construct agent: No reasoning strategy provided."
```

## Root cause

`_build_for_run` in
`packages/agentforge/src/agentforge/cli/run_cmd.py` built the replay
Agent without threading any of the configured agent settings:

```python
return Agent(model=replay_llm, memory=memory), replay_pipeline
```

Replay re-drives the *same* reasoning loop against the recorded
responses (`ReplayLLMClient`), so it needs the same strategy the
original run used. `Agent.__init__` rejects construction when no
strategy is resolvable, so the replay path raised before running.

The non-replay path (`build_agent_from_config`) passes
`strategy`/`budget_usd`/`system_prompt`/`max_iterations` from config;
the replay path simply forgot to. The bug went unnoticed because the
only `--replay` test (`test_run_replay_without_memory_errors`) covered
the *no-memory* error branch — the happy path had no end-to-end test.

## Fix

Thread the configured agent settings into the replay Agent, mirroring
`build_agent_from_config`:

```python
strategy = config.agent.strategy if isinstance(config.agent.strategy, str) else None
return (
    Agent(
        model=replay_llm,
        memory=memory,
        strategy=strategy,
        system_prompt=config.agent.system_prompt,
        budget_usd=config.agent.budget.usd,
        max_iterations=config.agent.max_iterations,
    ),
    replay_pipeline,
)
```

## Verification

- New end-to-end regression test
  `test_run_replay_happy_path_reconstructs_agent_with_strategy` in
  `packages/agentforge/tests/unit/test_cli_run.py`: configures sqlite
  memory, `--record`s a run, then `--replay`s it and asserts exit 0 +
  the replayed output. Fails (exit 1, "No reasoning strategy provided")
  on the pre-fix code.
- Manually confirmed offline: replaying a seeded recording prints the
  full run summary (`run_id`, `finish_reason=completed`,
  `cost_usd=0.0031`, `tokens_in/out=287/41`) with no API key or network.
- `uv run pre-commit run --all-files` green (ruff, mypy --strict,
  bandit, coverage ≥ 90%).

## Notes

- A companion run-lifecycle fix ships alongside: `agentforge run` never
  closed the agent (and therefore its memory store) after a one-shot
  run. With an in-process `InMemoryStore` that was harmless, but a real
  backend leaked its connection — for sqlite the `aiosqlite` worker
  thread then raised "Event loop is closed" after the loop tore down,
  which `pytest` escalates to a test error. `_dispatch` now closes the
  agent in a `finally`. This only became reachable once `--record` /
  `--replay` exercised a configured store (bug-022 + this fix).
- Found while building the README demo gif, whose "it really runs,
  offline" beat uses `agentforge run --replay` against a recorded
  fixture. This bug (plus [bug-022](./bug-022-memory-from-config.md),
  which blocked rebuilding the recording's sqlite store from config)
  was in the way; both are prerequisites for that demo.
- Depends on bug-022 being fixed: a replay can only load its recording
  once `modules.memory` builds from config.
