"""Manifest value types for `agentforge add/swap/remove module` (feat-010b).

Each Tier-3 module ships a `manifest.yaml` at the root of its
package describing the side-effects `agentforge add module X` should
apply to a consuming agent's repo:

    # agentforge_memory_postgres/manifest.yaml
    category: memory
    name: postgres
    env_vars:
      - name: POSTGRES_DSN
        description: "Connection string"
        required: true
    templates:
      - source: db/migrations/0001_init.sql
        destination: db/migrations/agentforge/0001_init.sql
    config_block:
      modules:
        memory:
          driver: postgres
          config:
            dsn: "${POSTGRES_DSN}"
    next_steps:
      - "Set POSTGRES_DSN in your .env file."
      - "Run `agentforge db migrate` to apply the schema."

The applier serialises what it actually did into an `AppliedManifest`
state file at `.agentforge-state/manifests/<distribution>.yaml`, so
`agentforge remove module X` can reverse the application.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EnvVarEntry(BaseModel):
    """One env-var the module needs. Appended to `.env.example` on apply."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(min_length=1)
    description: str = ""
    required: bool = True
    default: str | None = None


class TemplateFile(BaseModel):
    """A file the module ships that gets copied into the agent repo."""

    model_config = ConfigDict(strict=True, extra="forbid")

    source: str = Field(min_length=1)
    """Path inside the module package (relative to the package root)."""

    destination: str = Field(min_length=1)
    """Path in the consuming repo (relative to cwd at `add` time)."""

    overwrite: bool = False
    """Whether to overwrite an existing destination. Default False —
    a pre-existing file aborts the apply with a clear error."""


class Manifest(BaseModel):
    """Parsed `manifest.yaml`. Source of truth for what `add` does."""

    model_config = ConfigDict(strict=True, extra="forbid")

    category: str = Field(min_length=1)
    """Module category (`memory`, `tools`, `providers`, etc.) —
    must match the entry-point group suffix."""

    name: str = Field(min_length=1)
    """Module name within the category (e.g. `postgres`)."""

    env_vars: list[EnvVarEntry] = Field(default_factory=list)
    templates: list[TemplateFile] = Field(default_factory=list)
    config_block: dict[str, Any] = Field(default_factory=dict)
    """A nested-dict snippet to deep-merge into `agentforge.yaml`."""

    next_steps: list[str] = Field(default_factory=list)
    """Free-form lines printed after a successful `add`."""


class AppliedEnvVar(BaseModel):
    """Record of an env var the applier appended to `.env.example`."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(min_length=1)
    line: str = Field(min_length=1)
    """The exact line written, so `remove` can match-and-strip it."""


class AppliedTemplate(BaseModel):
    """Record of a file the applier created."""

    model_config = ConfigDict(strict=True, extra="forbid")

    destination: str = Field(min_length=1)
    """Path relative to cwd; safe to `unlink` on `remove`."""


class AppliedManifest(BaseModel):
    """State file at `.agentforge-state/manifests/<distribution>.yaml`.

    Records exactly what `agentforge add module X` wrote, so
    `agentforge remove module X` can reverse it. Atomic at the
    individual-step level (each list reflects what *did* land);
    apply failures partway through still write the state for what
    succeeded so `remove` can clean up.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    distribution: str = Field(min_length=1)
    """The `agentforge-X` distribution name."""

    category: str = Field(min_length=1)
    name: str = Field(min_length=1)
    """Mirrors `Manifest.category` / `Manifest.name` for diagnostics."""

    env_vars: list[AppliedEnvVar] = Field(default_factory=list)
    templates: list[AppliedTemplate] = Field(default_factory=list)
    config_block_applied: bool = False
    """Whether the deep-merge into `agentforge.yaml` landed. Used by
    `remove` to know whether to attempt the reverse merge."""
