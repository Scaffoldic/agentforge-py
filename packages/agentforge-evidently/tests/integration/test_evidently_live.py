"""Live `EvidentlyHook` integration test (feat-009 v0.2 follow-up).

Run with:

    EVIDENTLY_PROJECT=test EVIDENTLY_REPORT_DIR=/tmp/reports \\
        uv run pytest -m live packages/agentforge-evidently/
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from agentforge_core.production.run_context import bind_run, new_run, reset_run
from agentforge_core.values.state import RunResult, Step


@pytest.mark.live
def test_evidently_live_writes_report(tmp_path: Path) -> None:
    project = os.environ.get("EVIDENTLY_PROJECT")
    if not project:
        pytest.skip("EVIDENTLY_PROJECT not set")
    report_dir = Path(os.environ.get("EVIDENTLY_REPORT_DIR", tmp_path))

    from agentforge_evidently import EvidentlyHook  # noqa: PLC0415

    hook = EvidentlyHook.from_config(project=project, report_dir=report_dir)
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

    written = report_dir / f"{ctx.run_id}.json"
    assert written.exists()
