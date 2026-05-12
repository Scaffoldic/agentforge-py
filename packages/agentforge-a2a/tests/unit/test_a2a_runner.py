"""Smoke tests for the runner protocols (feat-014)."""

from __future__ import annotations

from agentforge_a2a._runner import (
    A2AClientRunner,
    A2AServerRunner,
    _HTTPXClientRunner,
    _UvicornServerRunner,
)
from fastapi import FastAPI


def test_production_client_runner_constructs() -> None:
    """v0.2 follow-up: constructor is sync + cheap; the httpx
    client is allocated lazily on the first call."""
    runner = _HTTPXClientRunner()
    assert runner is not None


def test_production_server_runner_constructs() -> None:
    """v0.2 follow-up: constructor stores config; uvicorn.Server
    is built inside `serve()`."""
    runner = _UvicornServerRunner(FastAPI(), host="127.0.0.1", port=0)
    assert runner is not None


def test_protocols_are_importable() -> None:
    # Smoke: the Protocol classes are importable.
    assert A2AClientRunner is not None
    assert A2AServerRunner is not None
