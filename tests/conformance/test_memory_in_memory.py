"""InMemoryStore conformance — runs the shared `MemoryStore` suite.

The same suite is run by every memory driver that ships in feat-005
(`agentforge-memory-sqlite`, `-postgres`, `-surrealdb`, `-neo4j`).
"""

from __future__ import annotations

import pytest
from agentforge.memory import InMemoryStore
from agentforge_core.testing import run_memory_conformance


@pytest.mark.conformance
@pytest.mark.asyncio
async def test_in_memory_store_passes_conformance() -> None:
    store = InMemoryStore()
    try:
        await run_memory_conformance(store)
    finally:
        await store.close()
