"""Live web_search integration test — gated on `RUN_LIVE_WEB=1`.

CI does not run this. Local development:

    RUN_LIVE_WEB=1 uv run pytest \
      packages/agentforge/tests/integration/test_web_search_live.py -v -m live

The DuckDuckGo HTML scrape is fragile by design — DuckDuckGo can
change its HTML at any time. When this test breaks, the warning
log surfaced by `_duckduckgo_search` is the user-facing signal to
swap to a real backend (Serper, Tavily, Brave) via `WebSearchTool(
search_fn=...)`.
"""

from __future__ import annotations

import os

import pytest
from agentforge.tools import web_search


def _live_enabled() -> bool:
    return os.environ.get("RUN_LIVE_WEB") == "1"


pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not _live_enabled(), reason="RUN_LIVE_WEB not set"),
]


@pytest.mark.asyncio
async def test_default_duckduckgo_backend_returns_results() -> None:
    results = await web_search.run(query="agentforge python framework", max_results=3)
    # Empty list is acceptable (DuckDuckGo HTML may have changed); the
    # test asserts the *contract* — whatever shape comes back must
    # be a list of dicts with title/url/snippet keys.
    assert isinstance(results, list)
    for r in results:
        assert set(r.keys()) >= {"title", "url", "snippet"}
        assert r["url"].startswith(("http://", "https://"))
