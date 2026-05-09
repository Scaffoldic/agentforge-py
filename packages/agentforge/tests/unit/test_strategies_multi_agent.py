"""Unit tests for `MultiAgentSupervisor`."""

from __future__ import annotations

import pytest
from agentforge import InMemoryStore
from agentforge._testing import FakeLLMClient
from agentforge.runtime import RUNTIME_KEY, RuntimeContext
from agentforge.strategies import MultiAgentSupervisor, ReActLoop
from agentforge.strategies._base import get_runtime
from agentforge_core import BudgetPolicy
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.resolver import Resolver
from agentforge_core.values.messages import LLMResponse, TokenUsage
from agentforge_core.values.state import AgentState, Step

# ---- Fixtures ----


def _resp(content: str = "", *, cost: float = 0.001) -> LLMResponse:
    return LLMResponse(
        content=content,
        stop_reason="end_turn",
        usage=TokenUsage(input_tokens=5, output_tokens=3),
        cost_usd=cost,
        model="fake",
        provider="fake",
    )


def _state(fake: FakeLLMClient, *, budget: BudgetPolicy | None = None) -> AgentState:
    rt = RuntimeContext(
        llm=fake,
        tools=(),
        memory=InMemoryStore(),
        budget=budget if budget is not None else BudgetPolicy(usd=5.0, max_iterations=20),
    )
    return AgentState(run_id="r1", task="big task", metadata={RUNTIME_KEY: rt})


class _ScriptedWorker(ReasoningStrategy):
    """Worker that just appends a synthesize step with a fixed reply."""

    def __init__(self, reply: str = "worker output", *, raises: Exception | None = None) -> None:
        self.reply = reply
        self.raises = raises
        self.calls = 0

    async def run(self, state: AgentState) -> AgentState:
        self.calls += 1
        if self.raises is not None:
            raise self.raises
        rt = get_runtime(state)
        rt.budget.check()
        state.steps.append(Step(iteration=1, kind="synthesize", content=self.reply, cost_usd=0.0))
        return state


def _delegation(workers: list[tuple[str, str]]) -> str:
    """Build a JSON delegation plan."""
    items = [f'{{"worker": "{w}", "task": "{t}"}}' for w, t in workers]
    return '{"assignments": [' + ", ".join(items) + "]}"


# ---- Constructor validation ----


def test_constructor_rejects_empty_workers() -> None:
    with pytest.raises(ValueError, match="non-empty"):
        MultiAgentSupervisor(workers={})


def test_constructor_validates_max_parallel_workers() -> None:
    with pytest.raises(ValueError, match="max_parallel_workers"):
        MultiAgentSupervisor(workers={"a": _ScriptedWorker()}, max_parallel_workers=0)


def test_constructor_validates_max_rounds() -> None:
    with pytest.raises(ValueError, match="max_rounds"):
        MultiAgentSupervisor(workers={"a": _ScriptedWorker()}, max_rounds=0)


def test_registered_under_strategies_multi_agent() -> None:
    cls = Resolver.global_().resolve("strategies", "multi-agent")
    assert cls is MultiAgentSupervisor


# ---- Single-round happy path ----


@pytest.mark.asyncio
async def test_single_round_delegation_and_aggregation() -> None:
    """plan → 2 workers run → aggregate. 2 LLM calls (delegate + aggregate)."""
    fake = FakeLLMClient(
        responses=[
            _resp(_delegation([("researcher", "find facts"), ("writer", "draft summary")])),
            _resp("final aggregated answer"),
        ]
    )
    state = _state(fake)
    researcher = _ScriptedWorker(reply="facts found")
    writer = _ScriptedWorker(reply="summary drafted")
    await MultiAgentSupervisor(
        workers={"researcher": researcher, "writer": writer},
    ).run(state)

    assert fake.call_count == 2
    assert researcher.calls == 1
    assert writer.calls == 1
    delegates = [s for s in state.steps if s.kind == "delegate"]
    assert len(delegates) == 2
    synth = [s for s in state.steps if s.kind == "synthesize"]
    assert len(synth) == 1


# ---- Unknown worker filtering ----


@pytest.mark.asyncio
async def test_unknown_worker_in_plan_is_dropped() -> None:
    fake = FakeLLMClient(
        responses=[
            _resp(_delegation([("known", "do it"), ("ghost", "vanish")])),
            _resp("final"),
        ]
    )
    state = _state(fake)
    known = _ScriptedWorker()
    await MultiAgentSupervisor(workers={"known": known}).run(state)

    assert known.calls == 1
    delegates = [s for s in state.steps if s.kind == "delegate"]
    assert len(delegates) == 1


# ---- Empty plan → straight to aggregation ----


@pytest.mark.asyncio
async def test_empty_plan_skips_to_aggregation() -> None:
    fake = FakeLLMClient(
        responses=[
            _resp('{"assignments": []}'),
            _resp("answered without workers"),
        ]
    )
    state = _state(fake)
    worker = _ScriptedWorker()
    await MultiAgentSupervisor(workers={"a": worker}).run(state)
    assert worker.calls == 0
    assert fake.call_count == 2


# ---- Worker failure → recorded as delegate.error, supervisor continues ----


@pytest.mark.asyncio
async def test_worker_exception_is_caught_and_recorded() -> None:
    fake = FakeLLMClient(
        responses=[
            _resp(_delegation([("ok", "task1"), ("bad", "task2")])),
            _resp("aggregated despite one failure"),
        ]
    )
    state = _state(fake)
    ok = _ScriptedWorker(reply="ok output")
    bad = _ScriptedWorker(raises=RuntimeError("kaboom"))
    await MultiAgentSupervisor(workers={"ok": ok, "bad": bad}).run(state)

    delegates = [s for s in state.steps if s.kind == "delegate"]
    assert len(delegates) == 2
    error_steps = [s for s in delegates if isinstance(s.content, dict) and "error" in s.content]
    assert len(error_steps) == 1


# ---- All workers fail → supervisor stops looping, aggregates ----


@pytest.mark.asyncio
async def test_all_workers_fail_aggregates_with_no_outputs() -> None:
    fake = FakeLLMClient(
        responses=[
            _resp(_delegation([("a", "x"), ("b", "y")])),
            _resp("synthesised from errors"),
        ]
    )
    state = _state(fake)
    a = _ScriptedWorker(raises=ValueError("fail-a"))
    b = _ScriptedWorker(raises=ValueError("fail-b"))
    await MultiAgentSupervisor(
        workers={"a": a, "b": b},
        max_rounds=2,  # would loop again, but bails
    ).run(state)
    # Aggregation runs exactly once even though max_rounds=2
    synth = [s for s in state.steps if s.kind == "synthesize"]
    assert len(synth) == 1


# ---- Parse-error fallback ----


@pytest.mark.asyncio
async def test_invalid_delegation_json_yields_no_workers() -> None:
    fake = FakeLLMClient(
        responses=[
            _resp("not valid JSON"),
            _resp("aggregated without delegation"),
        ]
    )
    state = _state(fake)
    worker = _ScriptedWorker()
    await MultiAgentSupervisor(workers={"a": worker}).run(state)
    assert worker.calls == 0
    assert fake.call_count == 2


# ---- Code-fence stripping ----


@pytest.mark.asyncio
async def test_strips_code_fences_from_delegation() -> None:
    fenced = "```json\n" + _delegation([("a", "task1")]) + "\n```"
    fake = FakeLLMClient(responses=[_resp(fenced), _resp("done")])
    state = _state(fake)
    worker = _ScriptedWorker()
    await MultiAgentSupervisor(workers={"a": worker}).run(state)
    assert worker.calls == 1
    assert fake.call_count == 2


# ---- Budget split: each worker gets a fraction of remaining USD ----


@pytest.mark.asyncio
async def test_budget_split_proportional_among_workers() -> None:
    """Each worker's sub-budget caps spend at remaining/N."""
    captured_caps: list[float] = []

    class _BudgetCapturingWorker(ReasoningStrategy):
        async def run(self, state: AgentState) -> AgentState:
            rt = get_runtime(state)
            captured_caps.append(rt.budget.usd)
            return state

    fake = FakeLLMClient(
        responses=[
            _resp(_delegation([("w1", "t1"), ("w2", "t2"), ("w3", "t3")]), cost=0.5),
            _resp("done"),
        ]
    )
    state = _state(fake, budget=BudgetPolicy(usd=4.0, max_iterations=20))
    await MultiAgentSupervisor(
        workers={
            "w1": _BudgetCapturingWorker(),
            "w2": _BudgetCapturingWorker(),
            "w3": _BudgetCapturingWorker(),
        }
    ).run(state)
    # After delegate call (cost=0.5), remaining=3.5; split 3 ways = ~1.166 each
    assert len(captured_caps) == 3
    assert all(abs(c - (3.5 / 3)) < 1e-6 for c in captured_caps)


# ---- Recursive composition: worker is itself a ReActLoop ----


@pytest.mark.asyncio
async def test_worker_can_be_real_strategy() -> None:
    """Workers can be any ReasoningStrategy — exercise composition with ReActLoop."""
    fake = FakeLLMClient(
        responses=[
            # supervisor delegate plan
            _resp(_delegation([("solver", "subtask")])),
            # ReActLoop worker: terminates on first end_turn
            _resp("worker thinks and ends"),
            # supervisor aggregate
            _resp("final aggregated"),
        ]
    )
    state = _state(fake)
    await MultiAgentSupervisor(
        workers={"solver": ReActLoop(max_iterations=3)},
    ).run(state)
    assert fake.call_count == 3


# ---- Multi-round delegation: prior results fed back to supervisor ----


@pytest.mark.asyncio
async def test_multi_round_passes_prior_results_to_supervisor() -> None:
    """max_rounds=2 with successes — second delegate call sees prior outputs."""
    captured_messages: list[list[object]] = []

    def capture_delegate(system: str, messages: list[object], tools: object = None) -> LLMResponse:
        captured_messages.append(list(messages))
        # First call: assign work; second call: empty plan (so we exit cleanly)
        if len(captured_messages) == 1:
            return _resp(_delegation([("a", "round-1 task")]))
        return _resp('{"assignments": []}')

    fake = FakeLLMClient(responses=[capture_delegate, capture_delegate, _resp("aggregated")])
    state = _state(fake)
    worker = _ScriptedWorker(reply="round-1 result")
    await MultiAgentSupervisor(workers={"a": worker}, max_rounds=2).run(state)

    # Second delegate call must include an assistant message carrying
    # the prior worker output.
    assert len(captured_messages) == 2
    second_call_msgs = captured_messages[1]
    assert any(
        getattr(m, "role", None) == "assistant" and "round-1 result" in getattr(m, "content", "")
        for m in second_call_msgs
    )


# ---- Worker output extraction handles dict-content steps ----


@pytest.mark.asyncio
async def test_worker_output_extracted_from_dict_step_content() -> None:
    """Workers whose last step has dict content get serialised to JSON."""

    class _DictWorker(ReasoningStrategy):
        async def run(self, state: AgentState) -> AgentState:
            state.steps.append(Step(iteration=1, kind="synthesize", content={"answer": 42}))
            return state

    fake = FakeLLMClient(
        responses=[
            _resp(_delegation([("d", "do")])),
            _resp("aggregated"),
        ]
    )
    state = _state(fake)
    await MultiAgentSupervisor(workers={"d": _DictWorker()}).run(state)
    delegates = [s for s in state.steps if s.kind == "delegate"]
    assert len(delegates) == 1
    assert isinstance(delegates[0].content, dict)
    assert '"answer": 42' in str(delegates[0].content["output"])


# ---- Worker descriptions appear in the supervisor prompt ----


@pytest.mark.asyncio
async def test_worker_descriptions_passed_to_supervisor_prompt() -> None:
    """Custom descriptions show up in the delegate-prompt system text."""
    captured: list[str] = []

    def capture(system: str, messages: object, tools: object = None) -> LLMResponse:
        captured.append(system)
        return _resp(_delegation([("a", "t")]))

    fake = FakeLLMClient(responses=[capture, _resp("done")])
    state = _state(fake)
    await MultiAgentSupervisor(
        workers={"a": _ScriptedWorker()},
        worker_descriptions={"a": "expert assistant"},
    ).run(state)
    assert any("expert assistant" in s for s in captured)
