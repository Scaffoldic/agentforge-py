"""Unit tests for `WebSearchTool` / `web_search` (feat-004 chunk 3).

The default DuckDuckGo backend hits the network; live coverage is
gated on `RUN_LIVE_WEB=1` in `tests/integration/`. These unit tests
substitute a fake `search_fn` so the tool's contract is exercised
without touching the network.
"""

from __future__ import annotations

import asyncio

import pytest
from agentforge._tools.web_search import _parse_duckduckgo_html
from agentforge.tools import SearchResult, WebSearchTool
from pydantic import ValidationError


async def _fake_backend(query: str, *, max_results: int) -> list[SearchResult]:
    return [
        SearchResult(
            title=f"Result {i + 1} for {query}",
            url=f"https://example.com/{i + 1}",
            snippet=f"Snippet {i + 1}",
        )
        for i in range(max_results)
    ]


@pytest.mark.asyncio
async def test_returns_results_via_search_fn() -> None:
    tool = WebSearchTool(search_fn=_fake_backend)
    out = await tool.run(query="hello", max_results=3)
    assert len(out) == 3
    assert out[0]["title"] == "Result 1 for hello"
    assert out[0]["url"] == "https://example.com/1"


@pytest.mark.asyncio
async def test_max_results_default() -> None:
    tool = WebSearchTool(search_fn=_fake_backend)
    out = await tool.run(query="hello")
    assert len(out) == 5  # default is 5


@pytest.mark.asyncio
async def test_results_are_json_friendly_dicts() -> None:
    """The tool's return value is `list[dict]` (not Pydantic models)
    so the LLM contract stays simple."""
    tool = WebSearchTool(search_fn=_fake_backend)
    out = await tool.run(query="x", max_results=1)
    assert isinstance(out[0], dict)
    assert set(out[0].keys()) == {"title", "url", "snippet"}


@pytest.mark.asyncio
async def test_timeout_raises() -> None:
    async def _slow(query: str, *, max_results: int) -> list[SearchResult]:
        await asyncio.sleep(5)
        return []

    tool = WebSearchTool(search_fn=_slow, timeout_s=0.1)
    with pytest.raises(TimeoutError, match="timeout_s"):
        await tool.run(query="x")


# ---- Input validation ----


def test_input_schema_rejects_empty_query() -> None:

    with pytest.raises(ValidationError):
        WebSearchTool.input_schema.model_validate({"query": ""})


def test_input_schema_caps_max_results() -> None:

    with pytest.raises(ValidationError):
        WebSearchTool.input_schema.model_validate({"query": "x", "max_results": 100})


def test_input_schema_rejects_zero_max_results() -> None:

    with pytest.raises(ValidationError):
        WebSearchTool.input_schema.model_validate({"query": "x", "max_results": 0})


# ---- Constructor validation ----


def test_constructor_rejects_zero_timeout() -> None:
    with pytest.raises(ValueError, match="timeout_s"):
        WebSearchTool(timeout_s=0)


# ---- Tool surface ----


def test_capabilities_declared() -> None:
    tool = WebSearchTool(search_fn=_fake_backend)
    assert tool.capabilities == frozenset({"network"})


# ---- DuckDuckGo HTML parser (offline) ----


def test_duckduckgo_html_parser_extracts_results() -> None:
    """The HTML parser must extract title / url / snippet from a
    realistic-shaped DuckDuckGo response without hitting the network."""

    sample = """
    <div>
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A//example.com/a">
        Example Title
      </a>
      <a class="result__snippet">A snippet about example.</a>
    </div>
    <div>
      <a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A//example.com/b">
        Second
      </a>
      <a class="result__snippet">More content.</a>
    </div>
    """
    results = _parse_duckduckgo_html(sample, max_results=10)
    assert len(results) == 2
    assert results[0].title == "Example Title"
    assert results[0].url == "https://example.com/a"
    assert results[0].snippet == "A snippet about example."
    assert results[1].url == "https://example.com/b"


def test_duckduckgo_html_parser_respects_max_results() -> None:

    blocks = "\n".join(
        f'<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A//example.com/{i}">T{i}</a>'
        f'<a class="result__snippet">S{i}</a>'
        for i in range(10)
    )
    results = _parse_duckduckgo_html(blocks, max_results=3)
    assert len(results) == 3


def test_duckduckgo_html_parser_returns_empty_on_no_match() -> None:

    assert _parse_duckduckgo_html("<html>no matches</html>", max_results=5) == []
