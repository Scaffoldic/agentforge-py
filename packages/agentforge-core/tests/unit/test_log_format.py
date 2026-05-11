"""Unit tests for `agentforge_core.production.log_format` (feat-009 chunk 2)."""

from __future__ import annotations

import io
import json
import logging
import sys

import pytest
from agentforge_core.production.log_filter import RunIdFilter, install_run_id_filter
from agentforge_core.production.log_format import (
    JsonFormatter,
    install_json_formatter,
    uninstall_json_formatter,
)
from agentforge_core.production.run_context import bind_run, new_run, reset_run


@pytest.fixture(autouse=True)
def _isolate_root_logger():
    """Each test gets a fresh root logger state."""
    root = logging.getLogger()
    saved_handlers = list(root.handlers)
    saved_filters = list(root.filters)
    saved_level = root.level
    yield
    root.handlers = saved_handlers
    root.filters = saved_filters
    root.setLevel(saved_level)


def _format_record(level: int = logging.INFO, **extra) -> dict:
    record = logging.LogRecord(
        name="agentforge.test",
        level=level,
        pathname=__file__,
        lineno=42,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    for key, value in extra.items():
        setattr(record, key, value)
    out = JsonFormatter().format(record)
    return json.loads(out)


def test_basic_fields_present():
    payload = _format_record()
    assert payload["level"] == "INFO"
    assert payload["logger"] == "agentforge.test"
    assert payload["msg"] == "hello world"
    assert "ts" in payload


def test_ts_is_iso8601_with_z_suffix():
    payload = _format_record()
    ts = payload["ts"]
    assert ts.endswith("Z")
    assert "T" in ts


def test_run_id_included_when_filter_set_it():
    payload = _format_record(run_id="01HXTESTRUNID")
    assert payload["run_id"] == "01HXTESTRUNID"


def test_run_id_omitted_when_not_set():
    payload = _format_record()
    assert "run_id" not in payload


def test_extra_fields_pass_through():
    payload = _format_record(tool_name="web_search", duration_ms=1234)
    assert payload["tool_name"] == "web_search"
    assert payload["duration_ms"] == 1234


def test_reserved_stdlib_fields_excluded():
    payload = _format_record()
    for key in ("module", "filename", "lineno", "pathname", "process"):
        assert key not in payload


def _raise_boom() -> None:
    raise ValueError("boom")


def test_exception_captured():
    try:
        _raise_boom()
    except ValueError:
        exc_info = sys.exc_info()
    record = logging.LogRecord(
        name="t",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="failed",
        args=(),
        exc_info=exc_info,
    )
    payload = json.loads(JsonFormatter().format(record))
    assert "exc" in payload
    assert "ValueError: boom" in payload["exc"]


def test_install_json_formatter_attaches_handler():
    handler = install_json_formatter()
    assert handler in logging.getLogger().handlers
    assert isinstance(handler.formatter, JsonFormatter)


def test_install_is_idempotent():
    h1 = install_json_formatter()
    h2 = install_json_formatter()
    assert h1 is h2
    # Only one handler installed regardless of repeated calls.
    handlers_named = [
        h
        for h in logging.getLogger().handlers
        if getattr(h, "name", None) == "agentforge.json_handler"
    ]
    assert len(handlers_named) == 1


def test_uninstall_removes_handler():
    install_json_formatter()
    uninstall_json_formatter()
    handlers_named = [
        h
        for h in logging.getLogger().handlers
        if getattr(h, "name", None) == "agentforge.json_handler"
    ]
    assert handlers_named == []


def test_end_to_end_with_run_id_filter():
    """Install both filter + formatter, emit a log on a logger that has
    RunIdFilter attached, parse the JSON, assert run_id present.

    Note: logger filters only run for records emitted at that logger;
    they do NOT see records that propagate up from child loggers.
    Production setups can either install the filter on every logger
    that emits or attach it to a handler instead. For this smoke
    test we attach the filter to the test logger directly.
    """
    root = logging.getLogger()
    stream = io.StringIO()
    handler = install_json_formatter()
    handler.stream = stream
    test_logger = logging.getLogger("agentforge.test")
    install_run_id_filter(test_logger)

    ctx = new_run(task="t")
    token = bind_run(ctx)
    try:
        test_logger.info("an event")
    finally:
        reset_run(token)

    line = stream.getvalue().strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["msg"] == "an event"
    assert payload["run_id"] == ctx.run_id
    # Cleanup the filter we just installed.
    for f in list(test_logger.filters):
        if isinstance(f, RunIdFilter):
            test_logger.removeFilter(f)
    for f in list(root.filters):
        if isinstance(f, RunIdFilter):
            root.removeFilter(f)
