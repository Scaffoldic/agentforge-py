"""Shared CLI helper: build an `Agent` from `agentforge.yaml` (feat-017).

`agentforge run`, `eval`, `debug`, `db ...`, and `health` all need to
go from a config file on disk to a ready-to-run `Agent`. This module
centralises that wiring so each command stays small.

The helper:

1. Loads + validates the config (feat-012's `load_config`).
2. Resolves every module declared in `modules.*` and `agent.*` via
   the global `Resolver` (feat-010).
3. Instantiates each module with the per-entry `config` dict.
4. Hands the wired-up objects to `Agent(...)`.
5. Optionally installs the recording hook from feat-017 chunk 1
   when `enable_recording=True` is set.

Errors are surfaced as `ModuleError` so the CLI can map them to
deterministic exit codes (per feat-017 §4 — config invalid → 2).
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from agentforge_core.config.loader import load_config
from agentforge_core.config.schema import AgentForgeConfig
from agentforge_core.contracts.embedding import EmbeddingClient
from agentforge_core.contracts.evaluator import Evaluator
from agentforge_core.contracts.graph_store import GraphStore
from agentforge_core.contracts.llm import LLMClient
from agentforge_core.contracts.memory import MemoryStore
from agentforge_core.contracts.reranker import Reranker
from agentforge_core.contracts.vector_store import VectorStore
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.resolver import Resolver
from agentforge_core.values.retrieval import GraphExpansion

from agentforge.agent import Agent
from agentforge.memory import InMemoryStore
from agentforge.pipeline import Pipeline
from agentforge.retrieval import Retriever

if TYPE_CHECKING:
    from agentforge_core.contracts.tool import Tool


async def load_and_build(
    *,
    path: Path | str | None = None,
    env: str | None = None,
    overrides: list[str] | None = None,
    enable_recording: bool = False,
) -> Agent:
    """Load config (feat-012) and construct a wired `Agent`.

    Sole entrypoint every CLI command uses. Honours
    `AGENTFORGE_CONFIG` / `AGENTFORGE_ENV` env vars (resolved inside
    `load_config`); accepts dotted-path overrides like
    `agent.budget.usd=5.0`.
    """
    config = load_config(path, env=env, overrides=overrides)
    return await build_agent_from_config(config, enable_recording=enable_recording)


async def build_agent_from_config(
    config: AgentForgeConfig,
    *,
    enable_recording: bool = False,
) -> Agent:
    """Build an `Agent` from an already-loaded `AgentForgeConfig`.

    Splits out from `load_and_build` for tests + reuse — tests build
    a `AgentForgeConfig` directly and skip the YAML parse.
    """
    memory = build_memory_from_config(config)
    if memory is not None:
        await _maybe_init_schema(memory)
    evaluators = build_evaluators_from_config(config)
    pipeline = build_pipeline_from_config(config)
    retriever = build_retriever_from_config(config)
    llm = _resolve_llm(config)
    strategy = config.agent.strategy if isinstance(config.agent.strategy, str) else None

    return Agent(
        model=llm,
        memory=memory if memory is not None else InMemoryStore(),
        evaluators=evaluators,
        strategy=strategy,
        retriever=retriever,
        system_prompt=config.agent.system_prompt,
        budget_usd=config.agent.budget.usd,
        max_iterations=config.agent.max_iterations,
        record_runs=memory if enable_recording and memory is not None else None,
        pipeline=pipeline,
    )


def build_memory_from_config(config: AgentForgeConfig) -> MemoryStore | None:
    """Resolve + instantiate `modules.memory`. Returns None when absent."""
    if config.modules.memory is None:
        return None
    cls = _resolve_class("memory", config.modules.memory.driver)
    instance = _instantiate(cls, config.modules.memory.config)
    if not isinstance(instance, MemoryStore):
        msg = (
            f"Resolved memory driver {config.modules.memory.driver!r} "
            f"({cls.__name__}) does not implement MemoryStore."
        )
        raise ModuleError(msg)
    return instance


def build_evaluators_from_config(config: AgentForgeConfig) -> list[Evaluator]:
    """Resolve + instantiate every entry in `modules.evaluators`."""
    out: list[Evaluator] = []
    for entry in config.modules.evaluators:
        cls = _resolve_class("evaluators", entry.name)
        instance = _instantiate(cls, entry.config)
        if not isinstance(instance, Evaluator):
            msg = (
                f"Resolved evaluator {entry.name!r} ({cls.__name__}) does not implement Evaluator."
            )
            raise ModuleError(msg)
        out.append(instance)
    return out


def build_pipeline_from_config(config: AgentForgeConfig) -> Pipeline | None:
    """Resolve + instantiate `modules.pipeline.tasks` (feat-015).

    Returns ``None`` when the pipeline block is absent, disabled, or
    has no tasks. Each task name resolves under the `"tasks"`
    resolver category (register via
    `agentforge.resolver_register.register_task` or via an
    `agentforge.tasks` entry point).
    """
    from agentforge_core.contracts.task import Task as TaskBase  # noqa: PLC0415

    cfg = config.modules.pipeline
    if cfg is None or not cfg.enabled or not cfg.tasks:
        return None
    tasks: list[TaskBase] = []
    for entry in cfg.tasks:
        cls = _resolve_class("tasks", entry.name)
        instance = _instantiate(cls, entry.config)
        if not isinstance(instance, TaskBase):
            msg = f"Resolved task {entry.name!r} ({cls.__name__}) does not implement Task."
            raise ModuleError(msg)
        tasks.append(instance)
    return Pipeline(
        tasks,
        max_concurrent=cfg.max_concurrent,
        on_task_error=cfg.on_task_error,
    )


def build_retriever_from_config(config: AgentForgeConfig) -> Retriever | None:
    """Resolve + instantiate the top-level `retrieval:` block.

    feat-021 follow-up. Returns ``None`` when no `retrieval:`
    block is set. Otherwise resolves three sub-components:

    - ``retrieval.vector_store.driver`` → ``vector_stores``
      category → instantiated `VectorStore`.
    - ``retrieval.embedder.driver`` → ``embeddings`` category →
      instantiated `EmbeddingClient`.
    - ``retrieval.reranker.name`` (optional) → ``rerankers``
      category → instantiated `Reranker`.

    The three are wired into a `Retriever` with the top-level
    knobs (``top_k`` / ``over_fetch_factor`` / ``batch_size``)
    forwarded to its constructor.

    Raises:
        ModuleError: a referenced module isn't registered or
            its instance doesn't implement the expected ABC.
    """
    r = config.retrieval
    if r is None:
        return None

    store_cls = _resolve_class("vector_stores", r.vector_store.driver)
    store = _instantiate(store_cls, r.vector_store.config)
    if not isinstance(store, VectorStore):
        msg = (
            f"Resolved vector_store {r.vector_store.driver!r} "
            f"({store_cls.__name__}) does not implement VectorStore."
        )
        raise ModuleError(msg)

    embedder_cls = _resolve_class("embeddings", r.embedder.driver)
    embedder = _instantiate(embedder_cls, r.embedder.config)
    if not isinstance(embedder, EmbeddingClient):
        msg = (
            f"Resolved embedder {r.embedder.driver!r} "
            f"({embedder_cls.__name__}) does not implement EmbeddingClient."
        )
        raise ModuleError(msg)

    reranker: Reranker | None = None
    if r.reranker is not None:
        reranker_cls = _resolve_class("rerankers", r.reranker.name)
        reranker_instance = _instantiate(reranker_cls, r.reranker.config)
        if not isinstance(reranker_instance, Reranker):
            msg = (
                f"Resolved reranker {r.reranker.name!r} "
                f"({reranker_cls.__name__}) does not implement Reranker."
            )
            raise ModuleError(msg)
        reranker = reranker_instance

    graph_expansion: GraphExpansion | None = None
    if r.graph_expansion is not None:
        ge_cfg = r.graph_expansion
        graph_store_cls = _resolve_class("graph_stores", ge_cfg.store.driver)
        graph_store_instance = _instantiate(graph_store_cls, ge_cfg.store.config)
        if not isinstance(graph_store_instance, GraphStore):
            msg = (
                f"Resolved graph_store {ge_cfg.store.driver!r} "
                f"({graph_store_cls.__name__}) does not implement GraphStore."
            )
            raise ModuleError(msg)
        graph_expansion = GraphExpansion(
            store=graph_store_instance,
            max_hops=ge_cfg.max_hops,
            edge_types=tuple(ge_cfg.edge_types) if ge_cfg.edge_types is not None else None,
            text_property=ge_cfg.text_property,
            decay=ge_cfg.decay,
        )

    return Retriever(
        store=store,
        embedder=embedder,
        reranker=reranker,
        top_k=r.top_k,
        over_fetch_factor=r.over_fetch_factor,
        batch_size=r.batch_size,
        mode=r.mode,
        rrf_k=r.rrf_k,
        graph_expansion=graph_expansion,
    )


def build_tools_from_config(config: AgentForgeConfig) -> list[Tool]:
    """Resolve tools listed under `agent.tools` (string or dict form)."""
    from agentforge_core.contracts.tool import Tool as ToolBase  # noqa: PLC0415

    tools: list[ToolBase] = []
    for entry in config.agent.tools:
        name = entry if isinstance(entry, str) else next(iter(entry))
        cfg = {} if isinstance(entry, str) else entry[name]
        cls = _resolve_class("tools", name)
        instance = _instantiate(cls, cfg)
        if not isinstance(instance, ToolBase):
            msg = f"Resolved tool {name!r} ({cls.__name__}) does not implement Tool."
            raise ModuleError(msg)
        tools.append(instance)
    return tools


def _resolve_llm(config: AgentForgeConfig) -> LLMClient | str | None:
    """Pick the LLM definition out of `config.agent.model` /
    `config.providers["default"]`.

    We hand a string back to `Agent.__init__` when the model is a
    plain `"<provider>:<model>"` string — `Agent` already knows how
    to resolve that. When `agent.model` is missing but
    `providers["default"]` is present, we synthesize the string from
    the named-provider record.
    """
    raw = config.agent.model
    if isinstance(raw, str):
        return raw
    default = config.providers.get("default")
    if default is None or default.model is None:
        return None
    return f"{default.type}:{default.model}"


def _resolve_class(category: str, name: str) -> type:
    return Resolver.global_().resolve(category, name)


def _instantiate(cls: type, cfg: dict[str, Any]) -> Any:
    """Construct an instance of `cls` from a YAML config dict.

    Preference order:

    1. ``cls.from_config(**cfg)`` — keyword-friendly factory
       (preferred for new modules; matches the
       `SentenceTransformersReranker.from_config(*, model=...)`
       shape from feat-021).
    2. ``cls.from_config(cfg)`` — legacy dict-positional shape
       (no in-tree callers today; kept as a defensive fallback
       so externally-shipped modules that ship the older shape
       still load).
    3. ``cls(**cfg)`` — plain constructor.
    """
    from_config = getattr(cls, "from_config", None)
    if callable(from_config):
        try:
            return from_config(**cfg)
        except TypeError:
            return from_config(cfg)
    return cls(**cfg)


async def _maybe_init_schema(memory: MemoryStore) -> None:
    init = getattr(memory, "init_schema", None)
    if callable(init):
        await init()


__all__ = [
    "build_agent_from_config",
    "build_evaluators_from_config",
    "build_memory_from_config",
    "build_pipeline_from_config",
    "build_retriever_from_config",
    "build_tools_from_config",
    "load_and_build",
]
