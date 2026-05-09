"""`RunContext` and the `current_run()` ContextVar.

Per ADR-0010, every agent run carries a `run_id` propagated through
async tasks via `contextvars.ContextVar`. Every log line, every span,
every tool call, every claim record carries this id — there is no path
to a log line without one.

Generation: ULID (sortable, monotonic, 26 chars). Imported from
`python-ulid`.

Idempotency keys are derived from the run's `idempotency_seed` plus
caller-supplied parts. Same parts within the same run produce the same
key; different parts produce different keys; different runs produce
different keys for the same parts.
"""

from __future__ import annotations

import hashlib
from contextvars import ContextVar, Token
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from ulid import ULID


class RunContext(BaseModel):
    """Per-run correlation primitive bound to the current async task."""

    model_config = ConfigDict(strict=True, validate_assignment=True)

    run_id: str
    parent_run_id: str | None = None
    started_at: datetime
    idempotency_seed: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    def idempotency_key_for(self, *parts: object) -> str:
        """Stable key derived from `(idempotency_seed, *parts)`.

        Tools that mutate external state read this to safely retry within
        a single run. Same `parts` → same key; different `parts` →
        different key; different run → different key.

        Returns:
            64-hex-character SHA-256 digest.
        """
        joined = self.idempotency_seed
        for part in parts:
            joined += "|" + str(part)
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()


_current_run: ContextVar[RunContext | None] = ContextVar("agentforge_current_run", default=None)


def current_run() -> RunContext:
    """Return the live `RunContext` bound to this async task.

    Raises:
        RuntimeError: no run is active. `current_run()` is only callable
            from within an `Agent.run()` invocation.
    """
    ctx = _current_run.get()
    if ctx is None:
        raise RuntimeError(
            "No active RunContext. current_run() can only be called inside "
            "Agent.run() (or a tool / hook invoked from one)."
        )
    return ctx


def new_run(
    *,
    parent_run_id: str | None = None,
    task: str | None = None,
) -> RunContext:
    """Create a new `RunContext` with a fresh ULID `run_id`.

    Does NOT bind it to the ContextVar — call `bind_run` for that.
    """
    run_id = str(ULID())
    seed_input = f"{run_id}|{task or ''}"
    seed = hashlib.sha256(seed_input.encode("utf-8")).hexdigest()[:32]
    return RunContext(
        run_id=run_id,
        parent_run_id=parent_run_id,
        started_at=datetime.now(UTC),
        idempotency_seed=seed,
    )


def bind_run(ctx: RunContext) -> Token[RunContext | None]:
    """Bind a `RunContext` to the current async scope.

    Returns the `Token` that `reset_run` consumes. Always pair with
    `reset_run` in a try/finally to avoid leaking context across runs.
    """
    return _current_run.set(ctx)


def reset_run(token: Token[RunContext | None]) -> None:
    """Reset the ContextVar to its prior value.

    Pair with `bind_run`; safe to call exactly once per token.
    """
    _current_run.reset(token)
