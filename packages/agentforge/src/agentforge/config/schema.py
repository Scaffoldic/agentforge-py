"""Pydantic root models for `agentforge.yaml` (feat-001 partial schema)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class LoggingConfig(BaseModel):
    """`logging:` section of agentforge.yaml."""

    model_config = ConfigDict(strict=True, extra="forbid")

    level: str = "INFO"
    run_id_filter: bool = True
    format: str = "text"  # "text" | "json"


class AgentConfig(BaseModel):
    """`agent:` section of agentforge.yaml — feat-001 surface only."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str | None = None
    model: str | None = None
    strategy: str | None = None
    system_prompt: str | None = None
    budget_usd: float = Field(default=1.0, ge=0.0)
    max_iterations: int = Field(default=25, ge=1)


class AgentForgeConfig(BaseModel):
    """Root model — feat-001 surface only.

    feat-012 will widen this with `modules`, `providers`, `output`, etc.
    Subsequent features add sections additively (semver-minor bumps).
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    agent: AgentConfig = Field(default_factory=AgentConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
