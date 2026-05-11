"""`agent_factory` — safe Agent constructor for unit tests (feat-016).

Defaults: `MockLLMClient.deterministic("ok")`, no tools, in-memory
store, low budget (0.10 USD), low iteration cap (3). Override any
kwarg explicitly. The intent is fast, deterministic, isolated tests
— no network, no secrets, < 100 ms per case.
"""

from __future__ import annotations

from typing import Any

from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.contracts.tool import Tool
from agentforge_core.values.state import AgentState, Step

from agentforge.agent import Agent
from agentforge.memory import InMemoryStore
from agentforge.testing.llm import MockLLMClient


class _SingleStepStrategy(ReasoningStrategy):
    """Trivial strategy: makes a single LLM call, returns its content.

    The factory wires this in when no `strategy` override is passed
    so tests don't need to install feat-002's strategies just to
    exercise `Agent.run`. Real production agents pass an explicit
    strategy.
    """

    async def run(self, state: AgentState) -> AgentState:
        from agentforge.strategies._base import get_runtime  # noqa: PLC0415

        runtime = get_runtime(state)
        response = await runtime.llm.call(
            system="",
            messages=[],
            tools=None,
        )
        state.steps.append(
            Step(
                iteration=0,
                kind="observe",
                content=response.content,
                cost_usd=response.cost_usd,
            )
        )
        return state


def agent_factory(
    *,
    model: str | LLMClient | None = None,
    tools: list[Tool] | None = None,
    strategy: str | ReasoningStrategy | None = None,
    **overrides: Any,
) -> Agent:
    """Construct an `Agent` with safe test defaults.

    Equivalent to::

        Agent(
            model=model or MockLLMClient.deterministic("ok"),
            tools=tools or [],
            strategy=strategy or _SingleStepStrategy(),
            memory=InMemoryStore(),
            budget_usd=0.10,
            max_iterations=3,
            install_log_filter=False,
            **overrides,
        )

    The `install_log_filter=False` default keeps test runs from
    mutating root-logger handlers across the suite.
    """
    return Agent(
        model=model if model is not None else MockLLMClient.deterministic("ok"),
        tools=tools if tools is not None else [],
        strategy=strategy if strategy is not None else _SingleStepStrategy(),
        memory=overrides.pop("memory", None) or InMemoryStore(),
        budget_usd=overrides.pop("budget_usd", 0.10),
        max_iterations=overrides.pop("max_iterations", 3),
        install_log_filter=overrides.pop("install_log_filter", False),
        **overrides,
    )


__all__ = ["agent_factory"]
