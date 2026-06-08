# Testing Standards

Test rigour is non-negotiable. 90% coverage from day 1, enforced by
pre-commit. Test code is production code; same standards apply.

## Test classes and their roles

| Class | Path | What it verifies |
|---|---|---|
| **Unit** | `tests/unit/` | One function or method, in isolation, mocked dependencies |
| **Integration** | `tests/integration/` | Two or more modules collaborating, real fixtures, mocked external services |
| **Conformance** | `tests/conformance/` | Every driver of an ABC passes the same suite (per ADR-0007) |
| **Property** | `tests/property/` | Hypothesis-driven invariant checks (where the invariant is clear) |
| **Live** | `tests/live/` (or `@pytest.mark.live`) | Hits real providers; runs in CI on schedule, never in pre-commit |

## Coverage

- **Hard floor: 90%** on the diff. Pre-commit runs `pytest
  --cov=src/agentforge --cov-fail-under=90` and blocks below.
- Coverage measured on **business code only** — `tests/`, `__pycache__`,
  generated stubs, and `live/` paths excluded via `[tool.coverage.run]
  omit`.
- A coverage **ratchet** in CI fails any PR that drops main's coverage
  by more than 0.5% (cf. an earlier internal change pattern). Even when
  above 90%, regression is rejected.

## Configuration-driven, not hardcoded

This is a hard rule (per `.claude/standards/configuration.md`). Tests
must follow it:

- **Test inputs in YAML / JSON** under `tests/fixtures/`. Never
  hardcoded as Python literals.
- **Test expectations** in fixture files alongside inputs.
- **Mock LLM scripts** in `tests/fixtures/llm/<scenario>.jsonl` —
  loaded by `MockLLMClient.from_recording(...)` (per feat-016).
- **Configurable thresholds**: any number that might tune (timeout,
  retry count, concurrency cap) lives in `tests/conftest.py` reading
  from a YAML; never inline.

Example layout:

```
tests/
├── conftest.py                          shared fixtures, no test bodies
├── fixtures/
│   ├── agents/
│   │   └── code-reviewer.yaml           a full agentforge.yaml for the test agent
│   ├── llm/
│   │   ├── happy-path.jsonl             scripted MockLLMClient script
│   │   └── tool-error-recovery.jsonl
│   ├── findings/
│   │   └── golden-prs.yaml              expected findings per PR fixture
│   └── thresholds.yaml                   timeouts, retry counts, etc.
├── unit/
│   └── test_<module>_<aspect>.py
├── integration/
│   └── test_<flow>.py
├── conformance/
│   └── memory_store_conformance.py      shared suite all drivers run
├── property/
│   └── test_truncation_invariants.py
└── live/
    └── test_<provider>_smoke.py
```

## Fixtures

- **Pytest fixtures over global state.** Every dependency is injected.
- **`temp_*` fixtures** for isolated state (temp directories, in-memory
  stores) — cleanup automatic via fixture finalisation.
- **`mock_llm`, `mock_memory`, `fake_tool`** fixtures live in
  `tests/conftest.py` so every test file can request them.
- **`agent_factory`** fixture (per feat-016) constructs an `Agent` with
  test-safe defaults (`MockLLMClient.deterministic("ok")`, `tools=[]`,
  `budget_usd=0.10`, `max_iterations=3`).
- Fixtures **never call real APIs** unless declared in `tests/live/`.

## Conformance suites

Every ABC ships a **shared conformance suite** in `tests/conformance/`.
Every driver runs the same suite. The suite is part of the framework,
not the test code, and is exposed via `agentforge.testing` so external
modules can import it for their own drivers.

Example:

```python
# tests/conformance/test_memory_postgres.py
from agentforge.testing import run_memory_conformance
from agentforge_memory_postgres import PostgresMemoryStore

@pytest.mark.asyncio
async def test_postgres_conformance(postgres_container):
    async with PostgresMemoryStore(dsn=postgres_container.dsn) as store:
        await run_memory_conformance(store)
```

The conformance helper is built from feat-016's `run_memory_conformance`
and similar.

## Test naming

- Files: `test_<module>_<aspect>.py` for unit;
  `test_<flow>.py` for integration; `test_<driver>_<conformance>.py` for
  conformance.
- Functions: `test_<what>_<condition>` — describes what is verified
  under what condition.
  - Good: `test_budget_check_raises_when_usd_exceeded`
  - Bad: `test_1`, `test_budget`

## Determinism

- Tests must be deterministic. Random data uses a seeded RNG.
- Time-dependent tests use `freezegun` (Py) / fake timers (TS).
- ULID / UUID generation uses framework-provided test fixtures that
  return fixed values during tests.
- Async timing tests use mocked `asyncio.sleep` where possible.

## Speed

- Unit tests must run in **< 50ms each** on average. Sum target:
  the entire unit suite under 30s.
- Integration tests target **< 1s each** average; full suite under 3
  minutes.
- Live tests have no time budget but run in CI on a separate schedule.

## Sync vs async

- Async tests use `pytest-asyncio` (Python) with `@pytest.mark.asyncio`,
  or vitest's native async support (TS).
- Cross-task state propagation tests (e.g. `run_id` ContextVar) must
  spawn nested tasks to verify propagation, not just call once.

## What pre-commit runs

```bash
pytest tests/unit -q -x                              # fast-fail
pytest tests/integration -q -x -m "not live"         # exclude live
pytest --cov=src --cov-fail-under=90 -q              # coverage gate
```

What CI additionally runs:

```bash
pytest tests/live -q                                 # live providers
pytest tests/conformance --slow                      # full driver matrix
python scripts/coverage_ratchet.py                   # diff-vs-main ratchet
```

## Forbidden patterns

- **Skipping tests with `@pytest.skip` to "fix later".** Either delete or
  make pass.
- **`time.sleep()` in tests.** Use mocked time or async fakes.
- **Assertions inside fixtures.** Fixtures construct; tests assert.
- **Calling production network from tests** outside `tests/live/`.
- **Catching exceptions in tests to make them pass.** If the code
  raises, the test should expect the raise (`pytest.raises`).
- **Reading from `os.environ` in tests** without a fixture that
  isolates the environment.

## References

- [`docs/features/feat-016-testing-framework.md`](../../docs/features/feat-016-testing-framework.md)
- [`.claude/standards/configuration.md`](./configuration.md)
- ADR-0007 (ABC + Protocol — conformance verifies real behaviour)
- ADR-0014 (async-first)
