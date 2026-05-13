"""Live `StatsdHook` integration test (feat-009 v0.2 follow-up).

Gated by `@pytest.mark.live` and the `STATSD_HOST` env var so
the default unit gate skips it. Run with:

    # Listener on UDP/8125 in the background (netcat works)
    nc -ul 8125 &
    STATSD_HOST=127.0.0.1 STATSD_PORT=8125 \\
        uv run pytest -m live packages/agentforge-statsd/

Exercises the production runner end-to-end against a real
StatsD listener.
"""

from __future__ import annotations

import os

import pytest
from agentforge_core.values.state import RunResult, Step


@pytest.mark.live
def test_statsd_live_emits_to_real_listener() -> None:
    host = os.environ.get("STATSD_HOST")
    if not host:
        pytest.skip("STATSD_HOST not set")
    port = int(os.environ.get("STATSD_PORT", "8125"))

    from agentforge_statsd import StatsdHook  # noqa: PLC0415

    hook = StatsdHook.from_config(host=host, port=port, prefix="agentforge.live")
    try:
        hook(Step(iteration=0, kind="think", content="live", duration_ms=5))
        hook(
            RunResult(
                output="ok",
                cost_usd=0.001,
                tokens_in=1,
                tokens_out=1,
                run_id="r-live",
                duration_ms=10,
                finish_reason="completed",
            )
        )
    finally:
        hook.close()
