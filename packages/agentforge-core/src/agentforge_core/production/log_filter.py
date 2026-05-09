"""`RunIdFilter` — attach `run_id` to every log record.

Auto-installed on the root logger by `Agent.__init__` (per ADR-0010,
P4). Idempotent — multiple installs do not accumulate filters.

Disable via `logging.run_id_filter: false` in `agentforge.yaml`.
"""

from __future__ import annotations

import logging

from agentforge_core.production.run_context import _current_run

_FILTER_NAME = "agentforge.run_id_filter"


class RunIdFilter(logging.Filter):
    """Attach `run_id` from the active `RunContext` (or `"-"`) to records."""

    def __init__(self) -> None:
        super().__init__(name=_FILTER_NAME)

    def filter(self, record: logging.LogRecord) -> bool:
        ctx = _current_run.get()
        record.run_id = ctx.run_id if ctx is not None else "-"
        return True


def install_run_id_filter(logger: logging.Logger | None = None) -> RunIdFilter:
    """Install `RunIdFilter` on `logger` (root by default), idempotent.

    Returns the live filter (the existing one if already installed).
    """
    target = logger if logger is not None else logging.getLogger()
    for existing in target.filters:
        if isinstance(existing, RunIdFilter):
            return existing
    new_filter = RunIdFilter()
    target.addFilter(new_filter)
    return new_filter


def uninstall_run_id_filter(logger: logging.Logger | None = None) -> None:
    """Remove `RunIdFilter` from `logger` (root by default), if present."""
    target = logger if logger is not None else logging.getLogger()
    for existing in list(target.filters):
        if isinstance(existing, RunIdFilter):
            target.removeFilter(existing)
