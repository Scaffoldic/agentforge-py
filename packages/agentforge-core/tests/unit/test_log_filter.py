"""Unit tests for `RunIdFilter` and the install/uninstall helpers."""

from __future__ import annotations

import logging

import pytest
from agentforge_core.production.log_filter import (
    RunIdFilter,
    install_run_id_filter,
    uninstall_run_id_filter,
)
from agentforge_core.production.run_context import bind_run, new_run, reset_run


class _CaptureHandler(logging.Handler):
    """Captures emitted records into a list for assertion."""

    def __init__(self) -> None:
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


@pytest.fixture
def isolated_logger() -> tuple[logging.Logger, _CaptureHandler]:
    """Per-test logger with a capture handler. No root propagation."""
    logger = logging.getLogger(f"test.agentforge.log_filter.{id(object())}")
    logger.propagate = False
    logger.setLevel(logging.DEBUG)
    logger.filters.clear()
    for h in list(logger.handlers):
        logger.removeHandler(h)
    handler = _CaptureHandler()
    logger.addHandler(handler)
    return logger, handler


def test_filter_attaches_run_id_when_active(
    isolated_logger: tuple[logging.Logger, _CaptureHandler],
) -> None:
    logger, handler = isolated_logger
    install_run_id_filter(logger)
    ctx = new_run()
    token = bind_run(ctx)
    try:
        logger.info("hello")
    finally:
        reset_run(token)

    record = next(r for r in handler.records if r.getMessage() == "hello")
    assert getattr(record, "run_id", None) == ctx.run_id


def test_filter_attaches_dash_when_no_run(
    isolated_logger: tuple[logging.Logger, _CaptureHandler],
) -> None:
    logger, handler = isolated_logger
    install_run_id_filter(logger)
    logger.info("idle")
    record = next(r for r in handler.records if r.getMessage() == "idle")
    assert getattr(record, "run_id", None) == "-"


def test_install_is_idempotent(
    isolated_logger: tuple[logging.Logger, _CaptureHandler],
) -> None:
    logger, _ = isolated_logger
    a = install_run_id_filter(logger)
    b = install_run_id_filter(logger)
    assert a is b
    count = sum(1 for f in logger.filters if isinstance(f, RunIdFilter))
    assert count == 1


def test_uninstall_removes_filter(
    isolated_logger: tuple[logging.Logger, _CaptureHandler],
) -> None:
    logger, _ = isolated_logger
    install_run_id_filter(logger)
    uninstall_run_id_filter(logger)
    assert not any(isinstance(f, RunIdFilter) for f in logger.filters)


def test_uninstall_when_not_installed_is_noop(
    isolated_logger: tuple[logging.Logger, _CaptureHandler],
) -> None:
    logger, _ = isolated_logger
    uninstall_run_id_filter(logger)
    assert not any(isinstance(f, RunIdFilter) for f in logger.filters)


def test_install_default_targets_root() -> None:
    install_run_id_filter()
    try:
        root = logging.getLogger()
        assert any(isinstance(f, RunIdFilter) for f in root.filters)
    finally:
        uninstall_run_id_filter()
