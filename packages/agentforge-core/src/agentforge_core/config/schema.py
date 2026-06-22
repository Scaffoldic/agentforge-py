"""Locked root models for `agentforge.yaml` (feat-012).

feat-001 shipped a minimal schema (`agent` + `logging`). feat-012
widens it to the full §4.2 surface: nested `budget`, `modules`
section with sub-shapes (memory, graph, retriever, evaluators,
observability, tools, protocols), `providers` named registry, and
`output` config. Adding fields is additive (ADR-0007 minor bump).

The runtime `Agent(budget_usd=, max_iterations=)` kwargs from
feat-001 remain the locked Public API; they continue to drive
`BudgetPolicy` internally. The YAML field shape (`budget.usd` etc.)
is the data-side representation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_AppModelT = TypeVar("_AppModelT", bound=BaseModel)


def _normalise_named_entry(value: Any) -> Any:
    """Normalise the terse YAML sugar for `name + config` entries into the
    canonical mapping before strict validation (bug-019).

    Three shapes are accepted; the first two are sugar:

    - String form ``faithfulness`` → ``{"name": "faithfulness"}``
    - Single-key mapping ``{geval: {rubric: "..."}}`` →
      ``{"name": "geval", "config": {"rubric": "..."}}``
    - Canonical mapping ``{name: x, config: {...}}`` → returned unchanged.

    Anything else is returned untouched so the model's own validation
    raises a clear error. Used by `EvaluatorEntry` and `GuardrailEntry`,
    so every list that holds them (`modules.evaluators` and guardrails'
    `input` / `output` / `tool_gates`) accepts all three forms.
    """
    if isinstance(value, str):
        return {"name": value}
    if isinstance(value, dict) and "name" not in value and len(value) == 1:
        ((key, cfg),) = value.items()
        if isinstance(key, str):
            entry: dict[str, Any] = {"name": key}
            if cfg is not None:
                entry["config"] = cfg
            return entry
    return value


class BudgetConfig(BaseModel):
    """`agent.budget:` — nested budget shape per spec §4.1.

    All caps optional; runtime defaults preserved when omitted. The
    flat `agent.budget_usd: float` form from feat-001 is no longer
    valid in YAML — `agentforge config validate` will report it as
    an unknown field (set `agent.budget.usd:` instead).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    usd: float = Field(default=1.0, ge=0.0)
    max_tokens: int | None = Field(default=None, ge=1)
    error_streak_limit: int | None = Field(default=None, ge=1)


class AgentConfig(BaseModel):
    """`agent:` section — model, strategy, prompt, budget, etc."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str | None = None
    model: str | dict[str, Any] | None = None
    strategy: str | dict[str, Any] | None = None
    system_prompt: str | None = None
    system_prompt_file: Path | None = None
    tools: list[str | dict[str, Any]] = Field(default_factory=list)
    budget: BudgetConfig = Field(default_factory=BudgetConfig)
    max_iterations: int = Field(default=25, ge=1)
    llm_options: dict[str, Any] = Field(default_factory=dict)

    @field_validator("system_prompt_file", mode="before")
    @classmethod
    def _coerce_path(cls, value: Any) -> Any:
        # Strict mode rejects strings for Path; YAML loads as `str`,
        # so coerce here. None / Path stay as-is.
        if isinstance(value, str):
            return Path(value)
        return value


class LoggingConfig(BaseModel):
    """`logging:` — level, run-id filter toggle, format."""

    model_config = ConfigDict(strict=True, extra="forbid")

    level: str = "INFO"
    run_id_filter: bool = True
    format: str = "text"  # "text" | "json"


class ModuleEntry(BaseModel):
    """Generic `driver + config` shape used by the `modules.memory`,
    `modules.graph`, `modules.retriever` sections."""

    model_config = ConfigDict(strict=True, extra="forbid")

    driver: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class MemoryModuleConfig(ModuleEntry):
    """Alias of `ModuleEntry` for `modules.memory:` — distinct type so
    schema docs can attach memory-specific guidance."""


class GraphModuleConfig(ModuleEntry):
    """Alias of `ModuleEntry` for `modules.graph:`."""


class RetrieverModuleConfig(ModuleEntry):
    """Alias of `ModuleEntry` for `modules.retriever:` (legacy).

    .. deprecated:: 0.2
        Use the top-level `retrieval:` block (see
        :class:`RetrievalConfig`) instead. The legacy single-entry
        form remains valid for v0.2 backward compatibility and may
        be removed in v1.0.
    """


class RerankerEntry(BaseModel):
    """`retrieval.reranker:` — name + config for a `Reranker` impl.

    Resolved against the `rerankers` entry-point category. Name
    matches the registered entry-point name (e.g.
    `sentence-transformers`).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class GraphExpansionConfig(BaseModel):
    """`retrieval.graph_expansion:` — wiring for GraphRAG hybrid
    retrieval (feat-023).

    The `store` field resolves against the `graph_stores`
    entry-point category. When set on a `RetrievalConfig`, the
    builder constructs a `GraphExpansion` value and forwards it
    into the `Retriever` constructor so vector / hybrid hits get
    augmented with N-hop graph neighbours.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    store: ModuleEntry
    max_hops: int = Field(default=2, ge=1)
    edge_types: list[str] | None = None
    """Edge-type filter. YAML lists deserialize to `list[str]`;
    converted to a tuple by `build_retriever_from_config` before
    constructing the `GraphExpansion` value."""
    direction: Literal["out", "in", "any"] = "any"
    """Edge direction to follow during expansion (enh-005): `out`
    (callees / what-X-cites), `in` (callers / who-cites-X), or `any`
    (default — the original undirected `traverse` behaviour)."""
    text_property: str = "text"
    decay: float = Field(default=0.5, gt=0.0, le=1.0)


class RetrievalConfig(BaseModel):
    """Top-level `retrieval:` block (feat-021 follow-up).

    Models the full retrieval pipeline: a `VectorStore` + an
    `EmbeddingClient` + an optional `Reranker`, plus retrieval-
    time knobs (`top_k`, `over_fetch_factor`, `batch_size`).
    Lives at the root of `agentforge.yaml`, not nested under
    `modules:`.

    The legacy `modules.retriever` single-entry form still works
    for v0.2 backward compat; the new `retrieval:` block
    supersedes it. Both should not be set simultaneously — the
    builder picks `retrieval:` when present.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    vector_store: ModuleEntry
    embedder: ModuleEntry
    reranker: RerankerEntry | None = None
    top_k: int = Field(default=5, ge=1)
    over_fetch_factor: int = Field(default=3, ge=1)
    batch_size: int = Field(default=32, ge=1)
    mode: Literal["vector", "hybrid"] = "vector"
    """Retrieval mode (feat-022): ``"vector"`` for cosine-only or
    ``"hybrid"`` for BM25 + cosine fused via RRF. Hybrid requires the
    underlying ``VectorStore`` to declare the ``"hybrid_search"``
    capability."""
    rrf_k: int = Field(default=60, ge=1)
    """RRF constant (Cormack 2009 default 60). Ignored when ``mode``
    is ``"vector"``."""
    graph_expansion: GraphExpansionConfig | None = None
    """Optional graph-augmented retrieval (feat-023). When set the
    builder resolves the graph store, constructs a
    :class:`GraphExpansion`, and forwards it to ``Retriever`` so
    vector / hybrid hits get expanded with N-hop graph neighbours.
    Composes orthogonally with ``mode`` and ``reranker``."""


class EvaluatorEntry(BaseModel):
    """An entry in `modules.evaluators:`. Three YAML shapes are valid:

    - String form: `- faithfulness` (just the name).
    - Single-key mapping: `- faithfulness: {cost_cap_usd: 0.05, ...}`.
    - Canonical mapping: `- {name: faithfulness, config: {...}}`.

    The first two are sugar; a `mode="before"` validator normalises them
    to `EvaluatorEntry(name=..., config={...})` before strict validation.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_sugar(cls, value: Any) -> Any:
        return _normalise_named_entry(value)


class ObservabilityEntry(BaseModel):
    """An entry in `modules.observability:` — same shape as evaluator
    entries (name + config)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class GuardrailPolicy(BaseModel):
    """Framework-wide guardrail policy (feat-018).

    Read from `agentforge.yaml` under the top-level
    `guardrail_policy:` key. Defaults are conservative (per P6 —
    loud defaults). Lives here rather than in `values/guardrails.py`
    so the config-schema module doesn't have to reach into
    `values` (avoids an import cycle through `values.state`).
    The runtime `ValidationResult` remains in `values.guardrails`.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    on_input_violation: Literal["block", "redact", "warn", "allow"] = "block"
    on_output_violation: Literal["block", "redact", "warn", "allow"] = "redact"
    on_tool_violation: Literal["block", "warn"] = "block"
    audit_channel: str = "agentforge.audit"
    fail_open: bool = False


class GuardrailEntry(BaseModel):
    """One entry inside `modules.guardrails.{input,output,tool_gates}`.

    Three YAML shapes are valid (mirrors `EvaluatorEntry`):

    - String form: `- prompt_injection_basic` (just the name).
    - Single-key mapping: `- presidio: {entities: ["EMAIL_ADDRESS"]}`.
    - Canonical mapping: `- {name: presidio, config: {...}}`.

    The first two are sugar; a `mode="before"` validator normalises them
    to `GuardrailEntry(name=..., config={...})` before strict validation.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def _coerce_sugar(cls, value: Any) -> Any:
        return _normalise_named_entry(value)


class ChatHistoryDriverConfig(BaseModel):
    """`modules.chat.history:` — driver + config for a chat history
    store (feat-020)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    driver: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class ChatTruncationConfig(BaseModel):
    """`modules.chat.truncation:` — strategy + config (feat-020)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    strategy: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class ChatSessionConfig(BaseModel):
    """`modules.chat.session:` — per-session policy knobs (feat-020)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    per_turn_budget_usd: float | None = Field(default=None, ge=0.0)
    per_session_budget_usd: float | None = Field(default=None, ge=0.0)
    idempotency_window_s: float = Field(default=60.0, ge=0.0)
    concurrency: Literal["queue", "reject", "replace"] = "queue"
    persist_steps: bool = True
    """When True (default), intermediate `act` / `observe` agent steps
    are persisted to `ChatHistoryStore` as `role="assistant"` (with
    `tool_calls`) and `role="tool"` (with `tool_call_id`) turns
    respectively, in addition to the final assistant turn. Tool-using
    chat agents need this on for the next turn's prompt to reflect
    what tools ran. Opt out by setting to False when an external
    consumer reconstructs history from another source (bug-010)."""
    safety_mode: Literal["buffer-then-stream", "sentence-window", "stream-then-redact"] = (
        "buffer-then-stream"
    )
    """Output-guardrail policy on streamed assistant turns:

    - ``"buffer-then-stream"`` (default) — agent runs to completion;
      output validators see the full text once; the assembled response
      is then sentence-segmented for the wire. Existing v0.2 behaviour.
    - ``"sentence-window"`` (feat-020 v0.3) — for real per-token
      streaming, buffer tokens until a sentence boundary, run
      ``check_output`` over each completed sentence, emit the
      validated sentence as the next ``text`` chunk. Trades a small
      latency hit (visible chunks at sentence boundaries) for
      streaming-aware safety.
    - ``"stream-then-redact"`` (deferred) — currently an alias for
      ``sentence-window``. A future v0.3+ pass may add inline regex
      redaction without buffering.
    """


class ChatConfig(BaseModel):
    """`modules.chat:` — chat layer config (feat-020).

    `history` may be ``None`` (defaults to in-memory). `truncation`
    similarly defaults to `SlidingWindow(50)` when absent.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    history: ChatHistoryDriverConfig | None = None
    truncation: ChatTruncationConfig | None = None
    session: ChatSessionConfig = Field(default_factory=ChatSessionConfig)


class PipelineTaskEntry(BaseModel):
    """One entry inside `modules.pipeline.tasks` (feat-015).

    Mirrors `EvaluatorEntry` / `GuardrailEntry`: a name (resolver
    lookup under the `"tasks"` category) plus optional kwargs the
    task class receives at construction.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class PipelineConfig(BaseModel):
    """`modules.pipeline:` — deterministic-task DAG (feat-015).

    When ``enabled`` is True and ``tasks`` is non-empty, the runtime
    resolves each entry against the global resolver's ``tasks``
    category, builds a `Pipeline`, and wires it into the `Agent`.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    enabled: bool = True
    max_concurrent: int = Field(default=4, ge=1)
    on_task_error: Literal["continue", "fail"] = "continue"
    tasks: list[PipelineTaskEntry] = Field(default_factory=list)


class GuardrailsConfig(BaseModel):
    """`modules.guardrails:` — input / output / tool-call validators.

    `defaults: true` keeps the framework's built-in basic validators
    (prompt_injection_basic, pii_redact_basic, capability_check)
    installed alongside whatever's listed here. Disabling them is
    explicit and emits a startup warning per P6 (loud defaults).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    defaults: bool = True
    input: list[GuardrailEntry] = Field(default_factory=list)
    output: list[GuardrailEntry] = Field(default_factory=list)
    tool_gates: list[GuardrailEntry] = Field(default_factory=list)


class ModulesConfig(BaseModel):
    """`modules:` — every plug-and-play module the agent uses.

    Each section accepts either a single driver-with-config or a list
    of entries:

        modules:
          memory: {driver: postgres, config: {...}}
          evaluators: [faithfulness, {geval: {rubric: "..."}}]
          observability: [{name: otel, config: {endpoint: "..."}}]
          guardrails:
            input: [prompt_injection_basic]
            output: [pii_redact_basic]
            tool_gates: [capability_check]
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    memory: MemoryModuleConfig | None = None
    graph: GraphModuleConfig | None = None
    retriever: RetrieverModuleConfig | None = None
    evaluators: list[EvaluatorEntry] = Field(default_factory=list)
    observability: list[ObservabilityEntry] = Field(default_factory=list)
    tools: list[str | dict[str, Any]] = Field(default_factory=list)
    protocols: list[ObservabilityEntry] = Field(default_factory=list)
    guardrails: GuardrailsConfig = Field(default_factory=GuardrailsConfig)
    pipeline: PipelineConfig | None = None
    chat: ChatConfig | None = None


class ProviderConfig(BaseModel):
    """One entry in the `providers:` named registry.

    `type` is the entry-point name (e.g. `"anthropic"`, `"bedrock"`).
    `model` + extra kwargs are passed through to the provider's
    constructor. `options` carries per-call LLM options.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    type: str = Field(min_length=1)
    model: str | None = None
    options: dict[str, Any] = Field(default_factory=dict)
    config: dict[str, Any] = Field(default_factory=dict)


class OutputConfig(BaseModel):
    """`output:` — finding-variant defaults, renderer choice, thresholds."""

    model_config = ConfigDict(strict=True, extra="forbid")

    default_finding_variant: str = "simple"
    default_renderer: str = "scorecard"
    thresholds: dict[str, list[str]] = Field(default_factory=dict)


class AgentForgeConfig(BaseModel):
    """Root model — `agentforge.yaml` shape.

    Adding a field to this model (or any submodel) is a minor bump
    under ADR-0007; removing or renaming requires a major bump.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    agent: AgentConfig = Field(default_factory=AgentConfig)
    modules: ModulesConfig = Field(default_factory=ModulesConfig)
    retrieval: RetrievalConfig | None = None
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    guardrail_policy: GuardrailPolicy = Field(default_factory=GuardrailPolicy)
    app: dict[str, Any] = Field(default_factory=dict)
    """Reserved namespace for **application** config (enh-002, feat-026
    Phase 1). The framework accepts this subtree but does not interpret
    it: a consuming agent puts its own config here and validates it with
    its own Pydantic model via :meth:`app_as`. Every other top-level key
    stays strict (`extra="forbid"`), so framework-key typos are still
    caught. Values inside `app:` get `${ENV}` interpolation, env-file
    layering, dotted-path overrides, and `config show --resolved` for
    free — they ride the same loader passes as framework keys. The
    framework performs no *registered-schema* validation inside `app:`
    in Phase 1; that arrives in feat-026 Phase 2."""

    def app_as(self, model: type[_AppModelT], key: str | None = None) -> _AppModelT:
        """Validate and return an application-config subtree.

        `key=None` validates the whole `app:` mapping; otherwise the
        `app[key]` subtree (missing key → empty mapping, so the caller's
        model supplies its own defaults). The caller's model owns its own
        strictness, so app-key typos surface here — strictness is
        delegated into `app:`, not lost.

        Example::

            class GraphConfig(BaseModel):
                store: StoreConfig


            graph_cfg = cfg.app_as(GraphConfig, "graph")
        """
        raw = self.app if key is None else self.app.get(key, {})
        return model.model_validate(raw)
