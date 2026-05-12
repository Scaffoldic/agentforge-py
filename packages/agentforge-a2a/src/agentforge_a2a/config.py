"""`A2AConfig` — Pydantic schema for `modules.protocols[a2a].config:`
(feat-014).

`A2ABridge.from_config(config_dict)` validates the raw dict
against this schema before wiring peers + an optional server.
Strict / ``extra="forbid"`` per project convention.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from agentforge_a2a.values import A2AExposeConfig, A2APeerConfig


class A2AConfig(BaseModel):
    """Top-level shape of the A2A protocol's config block."""

    model_config = ConfigDict(strict=True, extra="forbid")

    peers: list[A2APeerConfig] = Field(default_factory=list)
    expose: A2AExposeConfig | None = None


__all__ = ["A2AConfig"]
