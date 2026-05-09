"""Integration test — full Agent lifecycle with a fake LLM + tool + memory.

Exercises the per-feature §4.1 user-facing surface in feat-001 against
real wiring: a `ReasoningStrategy` that calls a fake `LLMClient`, runs
a fake `Tool`, persists a `Claim` through `InMemoryStore`, and returns
a `RunResult`. Validates run_id propagation end-to-end.
"""

from __future__ import annotations

from typing import Any

import pytest
from agentforge import Agent, InMemoryStore
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.contracts.tool import Tool
from agentforge_core.production.run_context import current_run
from agentforge_core.values.claim import Claim
from agentforge_core.values.messages import LLMResponse, Message, TokenUsage, ToolSpec
from agentforge_core.values.state import AgentState, Step
from pydantic import BaseModel

# ---- Fakes ----


class _FakeLLM(LLMClient):
    def __init__(self) -> None:
        self.calls: int = 0

    async def call(
        self,
        system: str,
        messages: list[Message],
        tools: list[ToolSpec] | None = None,
    ) -> LLMResponse:
        self.calls += 1
        return LLMResponse(
            content=f"answer for: {messages[-1].content}",
            stop_reason="end_turn",
            usage=TokenUsage(input_tokens=10, output_tokens=5),
            cost_usd=0.001,
            model="fake",
            provider="fake",
        )

    async def close(self) -> None:
        pass


class _PingInput(BaseModel):
    target: str


class _PingTool(Tool):
    name = "ping"
    description = "Pings a target."
    input_schema = _PingInput

    async def run(self, target: str) -> dict[str, Any]:
        return {"target": target, "ok": True}


class _SimpleStrategy(ReasoningStrategy):
    """One LLM call + one tool call + one memory write per run."""

    def __init__(self, llm: LLMClient, tool: Tool, memory: InMemoryStore) -> None:
        self._llm = llm
        self._tool = tool
        self._memory = memory

    async def run(self, state: AgentState) -> AgentState:
        # Verify run_id is bound and matches state
        run_ctx = current_run()
        assert run_ctx.run_id == state.run_id

        # 1. Think
        response = await self._llm.call(
            "You are a careful assistant.",
            [Message(role="user", content=state.task)],
        )
        state.steps.append(
            Step(
                iteration=0,
                kind="think",
                content=response.content,
                tokens_in=response.usage.input_tokens,
                tokens_out=response.usage.output_tokens,
                cost_usd=response.cost_usd,
            )
        )

        # 2. Act (tool call)
        tool_result = await self._tool.run(target="example.com")
        state.steps.append(Step(iteration=1, kind="act", content=tool_result))

        # 3. Persist a claim
        claim = Claim(
            run_id=state.run_id,
            project="integration-test",
            agent="full-lifecycle",
            category="finding",
            payload={"answer": response.content, "tool_result": tool_result},
        )
        await self._memory.put(claim)

        # 4. Final observe
        state.steps.append(Step(iteration=2, kind="observe", content=response.content))
        return state


# ---- Test ----


@pytest.mark.asyncio
async def test_agent_full_lifecycle_with_fake_llm_tool_memory() -> None:
    llm = _FakeLLM()
    tool = _PingTool()
    memory = InMemoryStore()
    strategy = _SimpleStrategy(llm=llm, tool=tool, memory=memory)

    async with Agent(
        strategy=strategy,
        memory=memory,
        tools=[tool],
        budget_usd=2.0,
        install_log_filter=False,
    ) as agent:
        result = await agent.run("Ping example.com")

        # 1. RunResult shape
        assert result.output.startswith("answer for: Ping example.com")
        assert len(result.run_id) == 26
        assert result.duration_ms >= 0
        assert result.tokens_in == 10
        assert result.tokens_out == 5
        assert result.finish_reason == "completed"
        assert len(result.steps) == 3

        # 2. Strategy actually ran
        assert llm.calls == 1

        # 3. Claim persisted with the same run_id (queried before close)
        claims = await memory.query(run_id=result.run_id)
        assert len(claims) == 1
        assert claims[0].run_id == result.run_id
        assert claims[0].project == "integration-test"


@pytest.mark.asyncio
async def test_run_id_propagates_to_tool_via_current_run() -> None:
    """Tools must see the same run_id via current_run() that ends up on
    RunResult."""
    seen_ids: list[str] = []

    class _RunIdCapturingTool(Tool):
        name = "capture"
        description = "Captures the current run id."
        input_schema = _PingInput

        async def run(self, target: str) -> dict[str, Any]:
            seen_ids.append(current_run().run_id)
            return {"ok": True}

    class _SingleToolStrategy(ReasoningStrategy):
        def __init__(self, tool: Tool) -> None:
            self._tool = tool

        async def run(self, state: AgentState) -> AgentState:
            await self._tool.run(target="x")
            state.steps.append(Step(iteration=0, kind="observe", content="done"))
            return state

    tool = _RunIdCapturingTool()
    strategy = _SingleToolStrategy(tool=tool)
    async with Agent(strategy=strategy, install_log_filter=False) as agent:
        result = await agent.run("test")

    assert seen_ids == [result.run_id]
