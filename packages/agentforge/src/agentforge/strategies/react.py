"""`ReActLoop` — modern reasoning + acting loop.

Per feat-002 §4.3: a single LLM call per iteration that may return
zero or more *structured* tool calls. The loop terminates when the
LLM returns a response with no tool calls (modern Anthropic / OpenAI
tool-calling pattern — `stop_reason="end_turn"` with empty
`tool_calls`). No special "finish" tool is needed.

Step shape: each iteration produces one `think` step (the LLM's
content), one `act` step per tool call, and one `observe` step per
tool result. Tool-execution errors are surfaced to the LLM as
observations (counted toward `error_streak_limit`).
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from agentforge_core.contracts.tool import Tool
from agentforge_core.observability.tracing import get_tracer
from agentforge_core.values.chat import StreamingEvent
from agentforge_core.values.messages import Message
from agentforge_core.values.state import AgentState

from agentforge.resolver_register import register_strategy
from agentforge.strategies._base import StrategyBase, _events_for_new_steps, get_runtime

DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful AI assistant. You can use tools when they help "
    "answer the user's question. Provide a final answer without calling "
    "tools when you have everything you need."
)


@register_strategy("react")
class ReActLoop(StrategyBase):
    """Think → act → observe loop with structured tool calls.

    Per feat-002 §4.2 the constructor surface is locked at v0.1:

    Args:
        max_iterations: Per-loop iteration cap. If `None`, the
            strategy uses `BudgetPolicy.max_iterations` from the
            runtime context. The override applies only to this
            run; the agent's configured budget caps are preserved.
    """

    def __init__(self, *, max_iterations: int | None = None) -> None:
        self._max_iterations_override: int | None = max_iterations

    async def run(self, state: AgentState) -> AgentState:
        runtime = get_runtime(state)
        if self._max_iterations_override is not None:
            runtime.budget.max_iterations = self._max_iterations_override

        system_prompt = runtime.system_prompt or DEFAULT_SYSTEM_PROMPT
        tool_specs = [tool.to_spec() for tool in runtime.tools] if runtime.tools else None
        messages: list[Message] = [Message(role="user", content=state.task)]
        iteration = 0
        tracer = get_tracer()

        while True:
            with tracer.start_as_current_span(
                "strategy.iteration",
                attributes={
                    "agentforge.iteration": iteration,
                    "agentforge.strategy": "react",
                },
            ):
                self._check_guardrails(state)

                response = await self._call_llm(
                    state,
                    iteration=iteration,
                    system=system_prompt,
                    messages=messages,
                    tools=tool_specs,
                    kind="think",
                )

                # Modern termination: no tool calls means the LLM is done.
                if not response.tool_calls:
                    break

                # Record the assistant's turn for the next iteration's context.
                # `tool_calls` must round-trip so provider clients can emit
                # native tool-use blocks matching the subsequent tool result
                # (bug-009 — Bedrock Converse rejects orphaned toolResult).
                messages.append(
                    Message(
                        role="assistant",
                        content=response.content,
                        tool_calls=response.tool_calls,
                    )
                )

                # Dispatch every tool call the LLM emitted.
                for tool_call in response.tool_calls:
                    self._record_step(
                        state,
                        iteration=iteration,
                        kind="act",
                        content={
                            "tool": tool_call.name,
                            "arguments": tool_call.arguments,
                        },
                        tool_call=tool_call,
                    )

                    tool = _find_tool(runtime.tools, tool_call.name)
                    observation = await self._dispatch_tool(
                        tool, tool_call.name, dict(tool_call.arguments)
                    )
                    if observation.startswith("Error:"):
                        runtime.budget.record_error()
                    else:
                        runtime.budget.record_success()

                    self._record_step(
                        state,
                        iteration=iteration,
                        kind="observe",
                        content=observation,
                        tool_call=tool_call,
                    )
                    messages.append(
                        Message(
                            role="tool",
                            content=observation,
                            tool_call_id=tool_call.id,
                        )
                    )

                iteration += 1

        return state

    async def stream(self, state: AgentState) -> AsyncIterator[StreamingEvent]:
        """Per-iteration streaming override (feat-002 v0.3 polish).

        Mirrors :meth:`run` but yields a ``step`` `StreamingEvent`
        each time a step is appended to ``state.steps``. The terminal
        ``done`` event is yielded so ``Agent.stream`` can swallow it
        and emit its own canonical one carrying the full RunResult
        shape.

        Strategies that bypass `Agent.stream()` (e.g. unit tests) see
        the strategy-level done with ``run_id`` + ``cost_usd``.
        """
        runtime = get_runtime(state)
        if self._max_iterations_override is not None:
            runtime.budget.max_iterations = self._max_iterations_override

        system_prompt = runtime.system_prompt or DEFAULT_SYSTEM_PROMPT
        tool_specs = [tool.to_spec() for tool in runtime.tools] if runtime.tools else None
        messages: list[Message] = [Message(role="user", content=state.task)]
        iteration = 0
        before = len(state.steps)
        tracer = get_tracer()

        while True:
            with tracer.start_as_current_span(
                "strategy.iteration",
                attributes={
                    "agentforge.iteration": iteration,
                    "agentforge.strategy": "react",
                },
            ):
                self._check_guardrails(state)

                response = await self._call_llm(
                    state,
                    iteration=iteration,
                    system=system_prompt,
                    messages=messages,
                    tools=tool_specs,
                    kind="think",
                )
                for ev in _events_for_new_steps(state.steps, before):
                    yield ev
                before = len(state.steps)

                if not response.tool_calls:
                    break

                messages.append(
                    Message(
                        role="assistant",
                        content=response.content,
                        tool_calls=response.tool_calls,
                    )
                )

                for tool_call in response.tool_calls:
                    self._record_step(
                        state,
                        iteration=iteration,
                        kind="act",
                        content={
                            "tool": tool_call.name,
                            "arguments": tool_call.arguments,
                        },
                        tool_call=tool_call,
                    )
                    for ev in _events_for_new_steps(state.steps, before):
                        yield ev
                    before = len(state.steps)

                    tool = _find_tool(runtime.tools, tool_call.name)
                    observation = await self._dispatch_tool(
                        tool, tool_call.name, dict(tool_call.arguments)
                    )
                    if observation.startswith("Error:"):
                        runtime.budget.record_error()
                    else:
                        runtime.budget.record_success()

                    self._record_step(
                        state,
                        iteration=iteration,
                        kind="observe",
                        content=observation,
                        tool_call=tool_call,
                    )
                    for ev in _events_for_new_steps(state.steps, before):
                        yield ev
                    before = len(state.steps)

                    messages.append(
                        Message(
                            role="tool",
                            content=observation,
                            tool_call_id=tool_call.id,
                        )
                    )

                iteration += 1

        yield StreamingEvent(
            kind="done",
            content={
                "run_id": state.run_id,
                "cost_usd": float(runtime.budget.spent_usd),
            },
        )


def _find_tool(tools: tuple[Tool, ...], name: str) -> Tool | None:
    for tool in tools:
        if type(tool).name == name:
            return tool
    return None
