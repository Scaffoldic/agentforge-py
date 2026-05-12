"""Live integration test for `PostgresChatHistory` (feat-020 v0.2).

Gated by `@pytest.mark.live` and the `RUN_LIVE_POSTGRES_DSN` env var.
Default unit gate skips this; the CI `live` job runs it against a
Postgres `services:` container.

Boot up:

    docker run --rm -d -p 5432:5432 -e POSTGRES_PASSWORD=test postgres:16
    RUN_LIVE_POSTGRES_DSN=postgresql://postgres:test@localhost:5432/postgres \
      uv run pytest -m live packages/agentforge-chat-history-postgres/
"""

from __future__ import annotations

import os

import pytest
from agentforge_chat_history_postgres import PostgresChatHistory
from agentforge_core.testing import run_chat_history_conformance


@pytest.mark.live
@pytest.mark.asyncio
async def test_postgres_chat_history_live_conformance() -> None:
    dsn = os.environ.get("RUN_LIVE_POSTGRES_DSN")
    if not dsn:
        pytest.skip("RUN_LIVE_POSTGRES_DSN env var unset; skipping live test")
    store = await PostgresChatHistory.from_dsn(dsn)
    try:
        await run_chat_history_conformance(store)
    finally:
        await store.close()
