"""Module-side config schema validation (feat-012 §4.4).

Per spec §4.4, each module ships its own Pydantic config schema; the
framework composes them at load time so `modules.memory.config:`,
`modules.evaluators[*].config:`, etc. get validated against the
right shape.

Module convention: a class registered with the resolver MAY declare
a class-level attribute:

    class PostgresMemoryStore(MemoryStore):
        config_schema: ClassVar[type[BaseModel] | None] = PostgresMemoryConfig

The validator walks the resolved config's `modules.*` blocks, looks
each entry's class up in the resolver, reads `cls.config_schema`,
and runs `schema.model_validate(entry.config)` if present. Modules
without a schema (the common case) accept any dict — the resolver
still confirms the class is registered (fail-at-startup, P11).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import ValidationError

from agentforge_core.config.schema import (
    AgentForgeConfig,
    EvaluatorEntry,
    ModuleEntry,
    ObservabilityEntry,
    PipelineTaskEntry,
    RerankerEntry,
)
from agentforge_core.production.exceptions import ModuleError

if TYPE_CHECKING:
    from agentforge_core.resolver import Resolver


def validate_module_configs(
    cfg: AgentForgeConfig,
    *,
    resolver: Resolver | None = None,
    strict: bool = True,
) -> None:
    """Validate each `modules.*` block against its module's schema.

    Args:
        cfg: A loaded `AgentForgeConfig` (post-`load_config`).
        resolver: Resolver to look classes up in. Defaults to the
            global resolver.
        strict: When True (default), missing modules raise
            `ModuleError`. When False, missing modules are skipped
            (useful for `agentforge config validate` against a config
            that references not-yet-installed packages).

    Raises:
        ModuleError: a referenced module isn't registered (strict
            mode) or a config dict fails its module's schema.
    """
    # Late import — avoids a load-order cycle with the values /
    # contracts modules that the resolver pulls in.
    from agentforge_core.resolver import Resolver as _Resolver  # noqa: PLC0415

    r = resolver if resolver is not None else _Resolver.global_()

    if cfg.modules.memory is not None:
        _validate_one(r, "memory", cfg.modules.memory, strict=strict)
    if cfg.modules.graph is not None:
        _validate_one(r, "graph", cfg.modules.graph, strict=strict)
    if cfg.modules.retriever is not None:
        _validate_one(r, "retriever", cfg.modules.retriever, strict=strict)

    for eval_entry in cfg.modules.evaluators:
        _validate_named(r, "evaluators", eval_entry, strict=strict)
    for obs_entry in cfg.modules.observability:
        _validate_named(r, "hooks", obs_entry, strict=strict)
    for proto_entry in cfg.modules.protocols:
        _validate_named(r, "protocols", proto_entry, strict=strict)
    if cfg.modules.pipeline is not None:
        for task_entry in cfg.modules.pipeline.tasks:
            _validate_named(r, "tasks", task_entry, strict=strict)
    if cfg.modules.chat is not None:
        if cfg.modules.chat.history is not None:
            _validate_driver(
                r,
                "chat.history",
                cfg.modules.chat.history.driver,
                cfg.modules.chat.history.config,
                strict=strict,
            )
        if cfg.modules.chat.truncation is not None:
            _validate_driver(
                r,
                "chat.truncation",
                cfg.modules.chat.truncation.strategy,
                cfg.modules.chat.truncation.config,
                strict=strict,
            )

    if cfg.retrieval is not None:
        _validate_retrieval(r, cfg, strict=strict)


def _validate_one(
    resolver: Resolver,
    category: str,
    entry: ModuleEntry,
    *,
    strict: bool,
) -> None:
    """Validate a `driver + config`-shaped module entry."""
    try:
        cls = resolver.resolve(category, entry.driver)
    except ModuleError:
        if strict:
            raise
        return
    schema = _read_config_schema(cls)
    if schema is None:
        return
    try:
        schema.model_validate(entry.config)
    except ValidationError as exc:
        raise ModuleError(
            f"modules.{category}.config failed validation for driver "
            f"{entry.driver!r}: {exc.errors(include_url=False)}"
        ) from exc


def _validate_named(
    resolver: Resolver,
    category: str,
    entry: EvaluatorEntry | ObservabilityEntry | PipelineTaskEntry | RerankerEntry,
    *,
    strict: bool,
) -> None:
    """Validate a named-list entry (evaluators / observability /
    protocols)."""
    try:
        cls = resolver.resolve(category, entry.name)
    except ModuleError:
        if strict:
            raise
        return
    schema = _read_config_schema(cls)
    if schema is None:
        return
    try:
        schema.model_validate(entry.config)
    except ValidationError as exc:
        raise ModuleError(
            f"modules.{category}[{entry.name!r}].config failed validation: "
            f"{exc.errors(include_url=False)}"
        ) from exc


def _validate_retrieval(
    resolver: Resolver,
    cfg: AgentForgeConfig,
    *,
    strict: bool,
) -> None:
    """Validate the top-level `retrieval:` block (feat-021 follow-up)."""
    assert cfg.retrieval is not None
    _validate_one(resolver, "vector_stores", cfg.retrieval.vector_store, strict=strict)
    _validate_one(resolver, "embeddings", cfg.retrieval.embedder, strict=strict)
    if cfg.retrieval.reranker is not None:
        _validate_named(resolver, "rerankers", cfg.retrieval.reranker, strict=strict)


def _validate_driver(
    resolver: Resolver,
    category: str,
    name: str,
    config: dict[str, Any],
    *,
    strict: bool,
) -> None:
    """Validate a driver-by-name + config dict (feat-020 chat hook)."""
    try:
        cls = resolver.resolve(category, name)
    except ModuleError:
        if strict:
            raise
        return
    schema = _read_config_schema(cls)
    if schema is None:
        return
    try:
        schema.model_validate(config)
    except ValidationError as exc:
        raise ModuleError(
            f"modules.{category}.config failed validation for {name!r}: "
            f"{exc.errors(include_url=False)}"
        ) from exc


def _read_config_schema(cls: type) -> Any:
    """Pull `cls.config_schema` if declared. Tolerant — modules without
    one return `None` (any dict accepted)."""
    schema = getattr(cls, "config_schema", None)
    if schema is None:
        return None
    if not isinstance(schema, type):
        return None
    return schema
