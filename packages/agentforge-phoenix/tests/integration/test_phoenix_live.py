"""Live `PhoenixHook` integration test (feat-009 v0.2 follow-up).

Run with:

    docker run -p 6006:6006 arizephoenix/phoenix
    PHOENIX_ENDPOINT=http://localhost:6006 \\
        uv run pytest -m live packages/agentforge-phoenix/
"""

from __future__ import annotations

import os

import pytest
from agentforge_core.production.run_context import bind_run, new_run, reset_run
from agentforge_core.values.state import RunResult, Step


@pytest.mark.live
def test_phoenix_live_emits_events() -> None:
    endpoint = os.environ.get("PHOENIX_ENDPOINT")
    if not endpoint:
        pytest.skip("PHOENIX_ENDPOINT not set")

    from agentforge_phoenix import PhoenixHook  # noqa: PLC0415

    hook = PhoenixHook.from_config(endpoint=endpoint, project_name="agentforge.live")
    ctx = new_run(task="live")
    token = bind_run(ctx)
    try:
        hook(Step(iteration=0, kind="think", content="live", duration_ms=5))
        hook(
            RunResult(
                output="ok",
                cost_usd=0.001,
                tokens_in=1,
                tokens_out=1,
                run_id=ctx.run_id,
                duration_ms=10,
                finish_reason="completed",
            )
        )
    finally:
        reset_run(token)
        hook.close()
