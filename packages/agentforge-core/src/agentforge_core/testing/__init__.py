"""Testing utilities — conformance suites that every driver must pass.

Per ADR-0007 and feat-016, every ABC in `agentforge-core` ships a
shared conformance suite. External module packages (e.g.
`agentforge-memory-postgres`) import these helpers to verify their
drivers against the locked contract.

The suites live in core (rather than the runtime package) so module
authors only need `agentforge-core` to test conformance — they don't
have to depend on the full runtime.
"""

from __future__ import annotations

from agentforge_core.testing.conformance import (
    run_embedding_conformance,
    run_graph_conformance,
    run_input_validator_conformance,
    run_memory_conformance,
    run_output_validator_conformance,
    run_strategy_conformance,
    run_task_conformance,
    run_tool_gate_conformance,
    run_vector_conformance,
)

__all__ = [
    "run_embedding_conformance",
    "run_graph_conformance",
    "run_input_validator_conformance",
    "run_memory_conformance",
    "run_output_validator_conformance",
    "run_strategy_conformance",
    "run_task_conformance",
    "run_tool_gate_conformance",
    "run_vector_conformance",
]
