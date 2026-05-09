"""Unit tests for the `Agent` orchestrator."""

from __future__ import annotations

from pathlib import Path

import pytest
from agentforge import Agent, InMemoryStore
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.resolver import Resolver, register_provider
from agentforge_core.values.messages import LLMResponse, Message, ToolSpec
from agentforge_core.values.state import AgentState, RunResult, Step


class _NoOpStrategy(ReasoningStrategy):
    """Test-only strategy: emits one 'observe' step and returns."""

    async def run(self, state: AgentState) -> AgentState:
        state.steps.append(Step(iteration=0, kind="observe", content="hello world"))
        return state


# ---- Construction ----


def test_agent_without_strategy_raises_at_construction() -> None:
    with pytest.raises(ModuleError, match="No reasoning strategy"):
        Agent()


def test_agent_accepts_strategy_instance() -> None:
    agent = Agent(strategy=_NoOpStrategy())
    assert isinstance(agent.memory, InMemoryStore)


def test_agent_uses_provided_memory() -> None:
    custom = InMemoryStore()
    agent = Agent(strategy=_NoOpStrategy(), memory=custom)
    assert agent.memory is custom


def test_agent_default_budget_is_one_dollar() -> None:
    agent = Agent(strategy=_NoOpStrategy())
    assert agent.budget.usd == pytest.approx(1.0)


def test_agent_kwarg_budget_overrides_default() -> None:
    agent = Agent(strategy=_NoOpStrategy(), budget_usd=5.0)
    assert agent.budget.usd == pytest.approx(5.0)


def test_agent_kwarg_max_iterations_overrides_default() -> None:
    agent = Agent(strategy=_NoOpStrategy(), max_iterations=50)
    assert agent.budget.max_iterations == 50


def test_agent_string_model_without_provider_registered_raises() -> None:
    with pytest.raises(ModuleError, match="No LLM provider registered"):
        Agent(model="anthropic:claude-sonnet-4.7", strategy=_NoOpStrategy())


def test_agent_invalid_model_string_raises() -> None:
    with pytest.raises(ModuleError, match="Invalid model string"):
        Agent(model="just-a-name", strategy=_NoOpStrategy())


def test_agent_resolves_registered_provider_from_model_string() -> None:
    """When a provider package has registered itself under the
    `providers` resolver category, `Agent(model="<provider>:...")`
    instantiates that class with `model_id=...`."""

    @register_provider(f"_test_provider_{id(object())}")
    class _FakeProvider(LLMClient):
        def __init__(self, *, model_id: str) -> None:
            self.model_id = model_id

        async def call(
            self,
            system: str,
            messages: list[Message],
            tools: list[ToolSpec] | None = None,
        ) -> LLMResponse:
            raise NotImplementedError

        async def close(self) -> None: ...

    # Find the unique registration name we just created.
    registered = [
        name
        for cat, name in Resolver.global_()._registry
        if cat == "providers"
        if name.startswith("_test_provider_")
    ]
    assert registered, "fake provider should be registered"
    name = registered[-1]
    try:
        agent = Agent(
            model=f"{name}:my-model-id",
            strategy=_NoOpStrategy(),
        )
        assert isinstance(agent._llm, _FakeProvider)
        assert agent._llm.model_id == "my-model-id"
    finally:
        Resolver.global_()._registry.pop(("providers", name), None)


def test_agent_loads_config_from_explicit_path(tmp_path: Path) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("agent:\n  budget_usd: 7.5\n")
    agent = Agent(strategy=_NoOpStrategy(), config_path=yaml_path)
    assert agent.budget.usd == pytest.approx(7.5)


def test_kwarg_overrides_config_file(tmp_path: Path) -> None:
    yaml_path = tmp_path / "agentforge.yaml"
    yaml_path.write_text("agent:\n  budget_usd: 7.5\n")
    agent = Agent(strategy=_NoOpStrategy(), config_path=yaml_path, budget_usd=10.0)
    assert agent.budget.usd == pytest.approx(10.0)


# ---- Lifecycle ----


@pytest.mark.asyncio
async def test_run_produces_run_result_with_run_id() -> None:
    agent = Agent(strategy=_NoOpStrategy(), install_log_filter=False)
    result = await agent.run("hi")
    assert isinstance(result, RunResult)
    # ULID = 26 chars
    assert len(result.run_id) == 26
    assert len(result.steps) == 1
    assert result.steps[0].kind == "observe"


@pytest.mark.asyncio
async def test_run_extracts_output_from_last_step() -> None:
    agent = Agent(strategy=_NoOpStrategy(), install_log_filter=False)
    result = await agent.run("hi")
    assert result.output == "hello world"


@pytest.mark.asyncio
async def test_async_context_manager_closes() -> None:
    async with Agent(strategy=_NoOpStrategy(), install_log_filter=False) as agent:
        await agent.run("hi")
    # After exit, agent is closed.
    with pytest.raises(ModuleError, match="closed"):
        await agent.run("again")


@pytest.mark.asyncio
async def test_close_is_idempotent() -> None:
    agent = Agent(strategy=_NoOpStrategy(), install_log_filter=False)
    await agent.close()
    await agent.close()


@pytest.mark.asyncio
async def test_on_finish_hook_fires() -> None:
    seen: list[RunResult] = []

    def hook(result: RunResult) -> None:
        seen.append(result)

    agent = Agent(
        strategy=_NoOpStrategy(),
        on_finish=hook,
        install_log_filter=False,
    )
    result = await agent.run("hi")
    assert seen == [result]


@pytest.mark.asyncio
async def test_on_finish_async_hook_awaited() -> None:
    seen: list[RunResult] = []

    async def hook(result: RunResult) -> None:
        seen.append(result)

    agent = Agent(
        strategy=_NoOpStrategy(),
        on_finish=hook,
        install_log_filter=False,
    )
    result = await agent.run("hi")
    assert seen == [result]
