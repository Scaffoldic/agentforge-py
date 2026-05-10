"""`RuntimeContext` — per-run execution context shared with strategies.

Lives in `agentforge` (not `agentforge-core`) because it references
the framework's runtime concerns — `BudgetPolicy`, the active
`LLMClient`, the agent's tool catalogue, the active `MemoryStore`.
`agentforge-core` defines those contracts; `agentforge` consumes
them.

`Agent.run()` constructs a `RuntimeContext` per run and stores it
on `state.metadata` under `RUNTIME_KEY`. Strategies access it via
`agentforge.strategies._base.get_runtime(state)`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from agentforge_core.contracts.graph_store import GraphStore
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.memory import MemoryStore
from agentforge_core.contracts.tool import Tool
from agentforge_core.production.budget import BudgetPolicy

if TYPE_CHECKING:
    from agentforge.retrieval import Retriever

RUNTIME_KEY = "__agentforge_runtime__"
"""Documented key under `AgentState.metadata` where the runtime is bound."""


@dataclass(frozen=True, slots=True)
class RuntimeContext:
    """Per-run execution context.

    Constructed by `Agent.run()` once per run and bound to
    `state.metadata[RUNTIME_KEY]`. Strategies read via
    `get_runtime(state)`.

    Frozen — once bound, the context does not change for the
    duration of the run. `BudgetPolicy` is itself mutable (the
    strategy calls `.check()`, `.reserve()`, `.commit()`); the
    immutability here is on the *binding*, not on the budget's
    internal counters.
    """

    llm: LLMClient
    tools: tuple[Tool, ...]
    memory: MemoryStore
    budget: BudgetPolicy
    system_prompt: str | None = None
    retriever: Retriever | None = None
    """Optional RAG retriever (feat-007). Strategies that want to
    ground responses in indexed documents check `runtime.retriever
    is not None` and call `retriever.retrieve(query)`."""
    graph_store: GraphStore | None = None
    """Optional knowledge-graph store (feat-009). Strategies that want
    to traverse a graph during reasoning check `runtime.graph_store is
    not None` and call `graph_store.traverse(...)` or `.match(...)`.

    Usually unset for vanilla agents; populated when the user passes
    `Agent(graph_store=...)` or configures a graph driver via
    `agentforge.yaml`."""
