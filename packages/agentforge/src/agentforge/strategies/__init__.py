"""Reasoning strategies — ReAct, Plan-Execute, Tree-of-Thoughts, Multi-Agent.

All four shipped stable from v0.1 per feat-002 / ADR-0008.

Concrete implementations land in subsequent feat-002 chunks:

- `ReActLoop` — chunk 2
- `PlanExecuteLoop` — chunk 3
- `TreeOfThoughts` — chunk 4
- `MultiAgentSupervisor` — chunk 5

Chunk 1 (this commit) ships only `_StrategyBase` and the
`get_runtime` helper that strategies use to access the per-run
execution context.
"""

from __future__ import annotations

from agentforge.strategies._base import (
    StrategyBase,
    get_runtime,
)

__all__ = [
    "StrategyBase",
    "get_runtime",
]
