"""Conformance harnesses (feat-016).

Re-exports the ABC-conformance functions from
`agentforge_core.testing.conformance` so users have one canonical
import path. The actual harnesses live in `agentforge-core` because
they exercise contracts defined there.

Typical usage:

    from agentforge.testing import run_memory_conformance
    from my_pkg import MyMemoryStore

    async def test_my_driver() -> None:
        async with MyMemoryStore.from_url("...") as store:
            await run_memory_conformance(store)
"""

from __future__ import annotations

from agentforge_core.testing.conformance import (
    run_input_validator_conformance,
    run_memory_conformance,
    run_output_validator_conformance,
    run_strategy_conformance,
    run_tool_gate_conformance,
    run_vector_conformance,
)

__all__ = [
    "run_input_validator_conformance",
    "run_memory_conformance",
    "run_output_validator_conformance",
    "run_strategy_conformance",
    "run_tool_gate_conformance",
    "run_vector_conformance",
]
