# feat-016: Testing framework

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-016 |
| **Title** | Testing — `MockLLMClient`, fake tools, fixtures, conformance helpers |
| **Status** | shipped (Python — `agentforge.testing` namespace + `agentforge-testing` package) |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.1 |
| **Languages** | both |
| **Module package(s)** | `agentforge` (built-ins), `agentforge-testing` (richer helpers) |
| **Depends on** | feat-001, feat-003, feat-004 |
| **Blocks** | none |

---

## 1. Why this feature

A framework that's hard to test is a framework that ships bugs. LLM
agents are especially hard: real API calls are slow, expensive, and
non-deterministic; tools touch the network; pipelines have many moving
parts. Most teams either skip tests entirely (deferred pain) or build
their own mock infrastructure per agent (duplicated effort, drift).

The pain we have seen: an agent has 2,000 lines of business logic, 3
tests, all of them slow and flaky. A regression in tool argument parsing
ships to production because the only path that exercised it required
the real API.

## 2. Why it must ship as framework

- **Test fixtures depend on framework internals.** `MockLLMClient`
  must implement `LLMClient`; fake tools must implement `Tool`. Only
  the framework can provide impls that conform exactly.
- **Conformance helpers** (e.g. running a memory-store conformance suite
  against your custom driver) only make sense when shipped by the
  framework that defines the contracts.
- **`run_id`/budget propagation in tests** must work the same as
  production. Hand-rolled mocks miss the lifecycle.
- **Without framework ownership:** every team writes a slightly different
  mock LLM with subtly different behaviour, and tests pass for reasons
  unrelated to the production code path.

## 3. How derived agents benefit

- **MockLLMClient out of the box** — replay scripted responses; assert
  on tool-call sequences.
- **Fake tools in one line.** `FakeTool.fake("web_search", lambda q:
  "stub")` plugs into `Agent(tools=[...])`.
- **pytest fixtures** — `agent_factory()`, `mock_llm()`,
  `temp_memory_store()` — for fast unit tests.
- **Conformance suite as a function** — drop in your custom driver,
  call `run_memory_conformance(driver)`, ship with confidence.
- **Determinism by default.** Tests don't need network, don't need
  secrets, run in &lt; 100ms each.
- **Replay** — record a real LLM transcript once; replay forever
  without API calls.

## 4. Feature specifications

### 4.1 User-facing experience

```python
import pytest
from agentforge.testing import MockLLMClient, FakeTool, agent_factory

@pytest.fixture
def mock_llm():
    return MockLLMClient.from_script([
        {"text": "I need to search.", "tool_calls": [{"name": "web_search",
                                                       "args": {"q": "Spain population"}}]},
        {"text": "47.5 million.", "tool_calls": [], "stop_reason": "end_turn"},
    ])

async def test_population_lookup(mock_llm):
    web_search = FakeTool.fake("web_search", lambda q: "Spain has 47.5M people.")
    agent = agent_factory(model=mock_llm, tools=[web_search])
    result = await agent.run("How many people live in Spain?")
    assert "47.5 million" in result.output
    assert mock_llm.call_count == 2
    assert mock_llm.tool_calls_observed == [("web_search", {"q": "Spain population"})]

# Driver conformance — drop-in confidence
from agentforge.testing import run_memory_conformance
from my_pkg import MyMemoryStore

async def test_my_driver_conforms():
    async with MyMemoryStore.from_url("...") as store:
        await run_memory_conformance(store)
```

### 4.2 Public API / contract

```python
# agentforge/testing/llm.py
class MockLLMClient(LLMClient):
    @classmethod
    def from_script(cls, responses: list[ScriptedResponse]) -> "MockLLMClient": ...

    @classmethod
    def from_recording(cls, path: Path) -> "MockLLMClient":
        """Replay from a JSONL recording (see `record_llm` below)."""

    @classmethod
    def deterministic(cls, response: str) -> "MockLLMClient":
        """Always returns the same response."""

    @property
    def call_count(self) -> int: ...
    @property
    def tool_calls_observed(self) -> list[tuple[str, dict]]: ...

# agentforge/testing/tools.py
class FakeTool(Tool):
    @classmethod
    def fake(cls, name: str, fn: Callable, *, description: str = "") -> Tool: ...

# agentforge/testing/fixtures.py
def agent_factory(*, model=None, tools=None, **overrides) -> Agent:
    """Constructs an Agent with safe test defaults (in-memory store,
    no observability, low budget)."""

@pytest.fixture
async def temp_memory_store(): ...    # InMemoryStore + cleanup

# agentforge/testing/conformance.py
async def run_memory_conformance(store: MemoryStore) -> None: ...
async def run_llm_conformance(client: LLMClient) -> None: ...
async def run_tool_conformance(tool: Tool) -> None: ...
async def run_strategy_conformance(strategy: ReasoningStrategy) -> None: ...

# agentforge/testing/recording.py
async def record_llm(client: LLMClient, path: Path) -> LLMClient:
    """Wrap a real client; record every call to `path`. Replay with
    MockLLMClient.from_recording(path)."""
```

### 4.3 Internal mechanics

- `MockLLMClient` advances through scripted responses on each `.call()`.
- `record_llm` writes JSONL with `{request, response}` per call; replay
  matches by request hash (not by sequence) so reordered calls still work.
- Conformance helpers are real test runners — they use `assert`s and a
  small harness; no pytest dep at the framework level.
- `agent_factory` defaults: `MockLLMClient.deterministic("ok")`,
  `tools=[]`, `budget_usd=0.10`, `max_iterations=3` — fast, safe.

### 4.4 Module packaging

- `agentforge/testing/` ships in the runtime package — no extra install
  for fixtures and basic mocks.
- `agentforge-testing` (separate) ships richer helpers (eval-harness
  golden-set runner, snapshot diffing, recording analysis) for teams
  that want them.

### 4.5 Configuration

```yaml
# agentforge.testing.yaml — auto-loaded if AGENTFORGE_ENV=testing
agent:
  model: "mock:deterministic"
  budget:
    usd: 0.10
    max_iterations: 3
modules:
  memory:
    driver: "memory"
```

The string `"mock:deterministic"` resolves to `MockLLMClient.deterministic("...")`.

## 5. Plug-and-play & upgrade story

Always available. Conformance helpers expand as new ABCs land; their
APIs are stable so users don't have to update tests on framework bumps.

## 6. Cross-language parity

Identical surface in Python (pytest) and TS (vitest). Recording format
identical; recordings made in Python replay in TS and vice versa.

## 7. Test strategy

(this is the testing feature, so the test strategy is "we test the test
helpers")

- **Self-test:** `MockLLMClient` passes `run_llm_conformance(self)`.
- **Replay:** record against a real provider; the replay matches byte-
  for-byte.
- **Fixture isolation:** `agent_factory` doesn't leak global state across
  tests.
- **Conformance helpers smoke:** they reject obvious non-conformant impls
  (a `Tool` that doesn't implement `run`, etc.).

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| MockLLMClient drifts from real client behaviour | Conformance suite shared between mock and real |
| Recording format becomes a back-compat burden | Pin format version in JSONL header; old recordings still loadable |
| Should we ship a "VCR cassette" style with redaction? | Yes — basic redaction (`api_key`) by default; configurable |
| pytest vs unittest vs nose | Helpers framework-agnostic; pytest fixtures provided as a thin layer |

## 9. Out of scope

- Property-based testing harness. Use Hypothesis / fast-check directly.
- Load testing / chaos. Out of scope; integration tests use
  `MockLLMClient` for cost/speed.
- A web UI for managing recordings. Out of scope.

## 10. Implementation status (Python)

Shipped in PR #21 across the `agentforge` runtime package (the
v0.1 public test-helper surface at `agentforge.testing`) and a
new Tier-3 sister package `agentforge-testing` (richer helpers).

| Chunk | Commit | What landed |
|---|---|---|
| 1 | `6c69bbe` | `agentforge.testing` namespace + `MockLLMClient` (`from_script`, `deterministic`, `call_count`, `tool_calls_observed`) + re-exports of `FakeTool`, `FakeLLMClient`, `echo_response` |
| 2 | `72c4de5` | `agent_factory` (safe defaults) + pytest fixtures `mock_llm` / `temp_memory_store` + conformance re-exports (`run_memory_conformance`, `run_strategy_conformance`, `run_vector_conformance`) |
| 3 | `327e525` | `record_llm(real, path, redactions)` + `MockLLMClient.from_recording(path)` + `load_recording` + versioned JSONL header + default redactions (`api_key` / `authorization` / `bearer`) |
| 4 | `f007d1e` | New `agentforge-testing` package: `GoldenSetRunner` (exact / contains / regex / any_of), `assert_snapshot` (UPDATE_SNAPSHOTS env), `analyze_recording` → `RecordingStats` |
| 5 | (this PR) | Spec status + Implementation section + Runbook + roadmap + CHANGELOG + state |

### Deviations from the design

- **`agentforge._testing` (private) is retained as a compat shim.**
  feat-002 and other early-feature tests import
  `FakeLLMClient` / `FakeTool` / `echo_response` from
  `agentforge._testing`; the public namespace at
  `agentforge.testing` re-exports them so both import paths work
  in v0.x. New code uses the public namespace; the private one
  is documented in its docstring as legacy.
- **MockLLMClient does not yet pass `run_llm_conformance(self)`
  (spec §7).** There is no `LLMClient` conformance suite shipped
  in `agentforge-core` yet; adding one is a follow-up sub-feat.
  `MockLLMClient` satisfies the locked `LLMClient` ABC and is
  exercised by the existing tests directly.
- **`record_llm` matches by sequence, not request hash, on
  replay.** Each `request_hash` is persisted, but
  `MockLLMClient.from_recording` returns responses in on-disk
  order. The hash is exposed for callers that want hash-keyed
  replay; a follow-up can layer it on once a real consumer
  surfaces.
- **VCR-style cassettes** (spec §8). Basic redaction is in
  (api_key / authorization / bearer); a full configurable
  redaction pipeline is deferred.
- **TypeScript port** (spec §6). The Python implementation
  defines the recording format the TS port will mirror; TS
  delivery deferred.

### Module split

- `agentforge.testing` — public namespace inside the runtime
  package. `MockLLMClient`, `FakeTool`, `FakeLLMClient`,
  `echo_response`, `agent_factory`, fixtures, conformance
  re-exports, `record_llm` + `load_recording`.
- `agentforge-testing` — pip-installable Tier-3 package.
  `GoldenSetRunner`, `assert_snapshot`, `analyze_recording`.
  Workspace member; CI extended to run its tests + mypy + bandit.

## 11. Runbook

### Mock an LLM

```python
from agentforge.testing import MockLLMClient, agent_factory, FakeTool

llm = MockLLMClient.from_script([
    {"text": "thinking", "tool_calls": [{"name": "search",
                                          "args": {"q": "Spain"}}]},
    {"text": "47.5M", "stop_reason": "end_turn"},
])
agent = agent_factory(
    model=llm,
    tools=[FakeTool.fake("search", lambda **kw: "47.5M people")],
)
result = await agent.run("How many people live in Spain?")
assert "47.5M" in result.output
assert llm.tool_calls_observed == [("search", {"q": "Spain"})]
```

### Record + replay a real provider

```python
from agentforge.testing import record_llm, MockLLMClient
from agentforge_anthropic import AnthropicClient  # example provider

# 1. Record (run once with real credentials)
real = AnthropicClient(model_id="claude-sonnet-4-7")
wrapped = record_llm(real, "tests/cassettes/spain.jsonl")
# ... use `wrapped` in your test; cassette gets written

# 2. Replay (subsequent runs — no API calls)
mock = MockLLMClient.from_recording("tests/cassettes/spain.jsonl")
```

Cassettes are JSON Lines: header line carries `format_version`
and `redactions`, followed by one line per call with
`{request_hash, request, response}`. `api_key`, `authorization`,
and `bearer` keys are redacted by default. Pass
`redactions=("custom-key", ...)` to extend.

### Conformance-test your own driver

```python
from agentforge.testing import run_memory_conformance
from my_package import MyMemoryStore

async def test_my_driver_conforms() -> None:
    async with MyMemoryStore.from_url(...) as store:
        await run_memory_conformance(store)
```

### Golden-set regression

```python
from agentforge_testing import GoldenSetRunner

async def test_known_questions() -> None:
    runner = GoldenSetRunner.from_jsonl("tests/golden.jsonl")
    results = await runner.run(my_agent_factory)
    failures = [r for r in results if not r.passed]
    assert not failures, [r.detail for r in failures]
```

Fixture format:

```jsonl
{"task": "Capital of France?", "expected": "Paris"}
{"task": "Population of Spain?", "expected": {"contains": "47"}}
{"task": "Translate hello.", "expected": {"any_of": ["bonjour", "hola"]}}
```

### Snapshot a deterministic render

```python
from agentforge_testing import assert_snapshot

def test_scorecard_render() -> None:
    text = scorecard_renderer.render(finding)
    assert_snapshot(text, "tests/__snapshots__/scorecard.txt")
```

Re-record with `UPDATE_SNAPSHOTS=1 pytest`.

### Analyze a cassette

```python
from agentforge_testing import analyze_recording

stats = analyze_recording("tests/cassettes/spain.jsonl")
print(stats.call_count, stats.tokens_in, stats.tool_call_names)
```

## 12. References

- feat-001, feat-003, feat-004, feat-005, feat-008
- Prior art: pytest-recording, VCR.py
