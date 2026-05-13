"""Live `LangfuseHook` integration test (feat-009 v0.2 follow-up).

Gated by `@pytest.mark.live` and `LANGFUSE_PUBLIC_KEY` +
`LANGFUSE_SECRET_KEY` env vars. Run with:

    LANGFUSE_PUBLIC_KEY=pk-lf-... LANGFUSE_SECRET_KEY=sk-lf-... \\
        LANGFUSE_HOST=https://cloud.langfuse.com \\
        uv run pytest -m live packages/agentforge-langfuse/
"""

from __future__ import annotations

import os

import pytest
from agentforge_core.production.run_context import bind_run, new_run, reset_run
from agentforge_core.values.state import RunResult, Step


@pytest.mark.live
def test_langfuse_live_emits_trace() -> None:
    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    if not public_key or not secret_key:
        pytest.skip("LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set")
    host = os.environ.get("LANGFUSE_HOST")

    from agentforge_langfuse import LangfuseHook  # noqa: PLC0415

    hook = LangfuseHook.from_config(
        public_key=public_key,
        secret_key=secret_key,
        host=host,
        trace_name_prefix="agentforge.live",
    )
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
