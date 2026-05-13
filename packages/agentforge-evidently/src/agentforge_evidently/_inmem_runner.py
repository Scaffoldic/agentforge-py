"""In-memory `EvidentlyRunner` for unit tests + downstream integration.

Records added rows + every report build + every report write
to disk-or-not (the fake honours `path` but doesn't write).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class FakeEvidentlyRunner:
    """In-memory recorder of every Evidently call."""

    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self.reports: list[dict[str, Any]] = []
        self.writes: list[tuple[Path, dict[str, Any]]] = []
        self.closed = False

    def add_record(self, record: dict[str, Any]) -> None:
        self.records.append(dict(record))

    def build_report(
        self,
        records: list[dict[str, Any]],
        *,
        project: str,
    ) -> dict[str, Any]:
        report = {"project": project, "records": [dict(r) for r in records]}
        self.reports.append(report)
        return report

    def write_report(
        self,
        report: dict[str, Any],
        *,
        path: Path,
    ) -> None:
        self.writes.append((path, dict(report)))

    def close(self) -> None:
        self.closed = True


__all__ = ["FakeEvidentlyRunner"]
