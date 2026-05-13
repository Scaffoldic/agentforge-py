"""Evidently runner Protocol + production SDK wrapper.

The Protocol abstracts (a) accumulating per-step records and
(b) producing a JSON report from the buffer. Production
runner builds an Evidently `Report` from a `pandas.DataFrame`
column-wise view of the records.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol


class EvidentlyRunner(Protocol):
    """Lifecycle Protocol for Evidently record + report emission."""

    def add_record(self, record: dict[str, Any]) -> None:  # pragma: no cover
        """Append one row to the in-flight buffer."""
        ...

    def build_report(
        self,
        records: list[dict[str, Any]],
        *,
        project: str,
    ) -> dict[str, Any]:  # pragma: no cover
        """Render an Evidently report from the buffered records."""
        ...

    def write_report(
        self,
        report: dict[str, Any],
        *,
        path: Path,
    ) -> None:  # pragma: no cover
        """Persist the report JSON to disk."""
        ...

    def close(self) -> None:  # pragma: no cover
        """Release the underlying SDK client."""
        ...


class _EvidentlyClientRunner:  # pragma: no cover — exercised only with `-m live`.
    """Production runner using the Evidently SDK."""

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def add_record(self, record: dict[str, Any]) -> None:
        self._records.append(dict(record))

    def build_report(
        self,
        records: list[dict[str, Any]],
        *,
        project: str,
    ) -> dict[str, Any]:
        try:
            from evidently import ColumnMapping  # noqa: PLC0415
            from evidently.report import Report  # noqa: PLC0415
        except ImportError:
            # Defensive: at this point the SDK was importable when
            # _build_evidently_runner ran, but if it's been uninstalled
            # under us we fall back to a plain JSON dump rather than
            # crashing the run.
            return {"project": project, "records": records}
        import pandas as pd  # noqa: PLC0415

        df = pd.DataFrame(records) if records else pd.DataFrame()
        report = Report(metrics=[], options={})
        try:
            report.run(reference_data=None, current_data=df, column_mapping=ColumnMapping())
            return dict(report.as_dict())
        except Exception:  # pragma: no cover — SDK-specific
            return {"project": project, "records": records}

    def write_report(
        self,
        report: dict[str, Any],
        *,
        path: Path,
    ) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, default=str))

    def close(self) -> None:
        self._records.clear()


__all__ = ["EvidentlyRunner"]
