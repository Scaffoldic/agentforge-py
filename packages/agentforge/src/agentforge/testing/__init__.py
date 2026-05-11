"""Public testing API (feat-016).

`agentforge.testing` is the v0.1 public test-helper surface. It
ships scripted-response mocks, fake tools, an `agent_factory`
helper, pytest fixtures, conformance harnesses re-exported from
`agentforge_core.testing`, and recording / replay helpers.

Typical usage:

    from agentforge.testing import (
        MockLLMClient,
        FakeTool,
        agent_factory,
        run_memory_conformance,
    )

    async def test_population_lookup() -> None:
        llm = MockLLMClient.from_script([
            {"text": "I need to search.",
             "tool_calls": [{"name": "search", "args": {"q": "x"}}]},
            {"text": "47.5M", "stop_reason": "end_turn"},
        ])
        web = FakeTool.fake("search", lambda **kw: "47.5M")
        agent = agent_factory(model=llm, tools=[web])
        result = await agent.run("How many people live in Spain?")
        assert "47.5M" in result.output
        assert llm.call_count == 2

The private `agentforge._testing` namespace is preserved as a
compatibility shim for the framework's own pre-feat-016 internal
tests; new code should import from `agentforge.testing`.
"""

from __future__ import annotations

from agentforge._testing.fake_llm import FakeLLMClient, echo_response
from agentforge._testing.fake_tool import FakeTool
from agentforge.testing.conformance import (
    run_memory_conformance,
    run_strategy_conformance,
    run_vector_conformance,
)
from agentforge.testing.factory import agent_factory
from agentforge.testing.llm import MockLLMClient, ScriptedResponse

__all__ = [
    "FakeLLMClient",
    "FakeTool",
    "MockLLMClient",
    "ScriptedResponse",
    "agent_factory",
    "echo_response",
    "run_memory_conformance",
    "run_strategy_conformance",
    "run_vector_conformance",
]
