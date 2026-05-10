# feat-016: Testing framework

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-016 |
| **Title** | Testing — `MockLLMClient`, fake tools, fixtures, conformance helpers |
| **Status** | proposed |
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

## 10. References

- feat-001, feat-003, feat-004, feat-005, feat-008
- Prior art: pytest-recording, VCR.py
