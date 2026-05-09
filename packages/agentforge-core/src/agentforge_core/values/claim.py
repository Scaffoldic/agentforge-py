"""`Claim` — a persisted unit of agent-produced knowledge.

Written through `MemoryStore`. The `(project, agent)` pair namespaces
claims; cross-agent and cross-project queries are explicit verbs (per
feat-005 design). `id` is a ULID for sortable monotonic ordering.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from ulid import ULID


class Claim(BaseModel):
    """A persisted unit of agent-produced knowledge."""

    model_config = ConfigDict(frozen=True, strict=True)

    id: str = Field(default_factory=lambda: str(ULID()))
    run_id: str
    project: str
    agent: str
    category: str
    payload: dict[str, Any]
    supersedes: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)
