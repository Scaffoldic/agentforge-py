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
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
    """Alias of `ModuleEntry` for `modules.retriever:`."""


class EvaluatorEntry(BaseModel):
    """An entry in `modules.evaluators:`. Two YAML shapes are valid:

    - String form: `- faithfulness` (just the name).
    - Mapping form: `- faithfulness: {cost_cap_usd: 0.05, ...}`.

    We model the mapping form here; the loader normalises strings to
    `EvaluatorEntry(name=..., config={})` before validation.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class ObservabilityEntry(BaseModel):
    """An entry in `modules.observability:` — same shape as evaluator
    entries (name + config)."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(min_length=1)
    config: dict[str, Any] = Field(default_factory=dict)


class ModulesConfig(BaseModel):
    """`modules:` — every plug-and-play module the agent uses.

    Each section accepts either a single driver-with-config or a list
    of entries:

        modules:
          memory: {driver: postgres, config: {...}}
          evaluators: [faithfulness, {geval: {rubric: "..."}}]
          observability: [{name: otel, config: {endpoint: "..."}}]
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    memory: MemoryModuleConfig | None = None
    graph: GraphModuleConfig | None = None
    retriever: RetrieverModuleConfig | None = None
    evaluators: list[EvaluatorEntry] = Field(default_factory=list)
    observability: list[ObservabilityEntry] = Field(default_factory=list)
    tools: list[str | dict[str, Any]] = Field(default_factory=list)
    protocols: list[ObservabilityEntry] = Field(default_factory=list)


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
    providers: dict[str, ProviderConfig] = Field(default_factory=dict)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
