"""`JsonFormatter` — structured JSON log records for production.

Per feat-009 §4.5: `logging.format: "json"` switches `agentforge` to
emit one-JSON-object-per-line records, ready for ingestion by log
aggregators (Loki, CloudWatch, Datadog, etc.). Default stays `"text"`
to keep local development greppable.

The formatter respects whatever `RunIdFilter` added — `run_id` lands
on every record. Standard fields: `ts`, `level`, `logger`, `msg`,
`run_id`. Anything else attached to the record via `extra=` (or via
filters) is included verbatim.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any

_HANDLER_NAME = "agentforge.json_handler"

# LogRecord attributes set by stdlib that we don't want to leak into
# the JSON payload (already represented via dedicated fields, or
# internal).
_RESERVED: frozenset[str] = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per record.

    Output shape:
        {"ts": "2026-05-11T16:42:01.123Z",
         "level": "INFO",
         "logger": "agentforge.agent",
         "msg": "the message",
         "run_id": "01HX...",
         ...any custom extras...}
    """

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=UTC).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        # `run_id` lands here when `RunIdFilter` installed it.
        if hasattr(record, "run_id"):
            payload["run_id"] = record.run_id
        # Surface any extras the caller attached via `logger.info(..., extra={...})`.
        for key, value in record.__dict__.items():
            if key in _RESERVED or key in payload or key.startswith("_"):
                continue
            payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


def install_json_formatter(
    logger: logging.Logger | None = None,
    *,
    level: int = logging.INFO,
) -> logging.Handler:
    """Attach a `StreamHandler` with `JsonFormatter` to `logger` (root
    by default). Idempotent — repeated calls return the existing
    handler.

    Returns the handler so callers can adjust level / stream.
    """
    target = logger if logger is not None else logging.getLogger()
    for existing in target.handlers:
        if getattr(existing, "name", None) == _HANDLER_NAME:
            return existing
    handler = logging.StreamHandler()
    handler.name = _HANDLER_NAME
    handler.setLevel(level)
    handler.setFormatter(JsonFormatter())
    target.addHandler(handler)
    if target.level == logging.NOTSET or target.level > level:
        target.setLevel(level)
    return handler


def uninstall_json_formatter(logger: logging.Logger | None = None) -> None:
    """Remove the JSON handler if present (idempotent)."""
    target = logger if logger is not None else logging.getLogger()
    for existing in list(target.handlers):
        if getattr(existing, "name", None) == _HANDLER_NAME:
            target.removeHandler(existing)
