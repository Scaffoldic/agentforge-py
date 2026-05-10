"""`web_search` — pluggable web-search tool (feat-004).

The default backend is a DuckDuckGo HTML scrape — fragile but
dependency-free. Real backends (Serper, Tavily, Brave) ship as
separate module packages later. Users can swap in any callable:

    from agentforge.tools import WebSearchTool

    async def my_backend(query: str, *, max_results: int) -> list[SearchResult]:
        ...

    custom = WebSearchTool(search_fn=my_backend)
    agent = Agent(tools=[custom, ...])

Capabilities: `{"network"}`.

Live integration tests for the default DuckDuckGo backend are gated
on `RUN_LIVE_WEB=1`; CI does not run them. Unit tests substitute a
fake `search_fn` so the tool itself can be exercised without
network access.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any, ClassVar
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from urllib.request import Request, urlopen

from agentforge_core.contracts.tool import Tool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (compatible; agentforge/0.1; +https://github.com/Scaffoldic/agentforge-py)"
)
_DEFAULT_TIMEOUT_S = 10.0
_DEFAULT_MAX_RESULTS = 5


class SearchResult(BaseModel):
    """A single web-search hit. The shape is provider-agnostic so
    different `search_fn` implementations can return the same type."""

    title: str
    url: str
    snippet: str = ""


class _WebSearchInput(BaseModel):
    """Input schema for `web_search`."""

    query: str = Field(min_length=1, description="The search query string.")
    max_results: int = Field(
        default=_DEFAULT_MAX_RESULTS,
        ge=1,
        le=20,
        description="Number of results to return (1-20).",
    )


SearchFn = Callable[..., Awaitable[list[SearchResult]]]


class WebSearchTool(Tool):
    """Web search via a pluggable backend.

    `search_fn` defaults to a DuckDuckGo HTML scraper — fragile;
    overridable. Custom backends should accept `(query: str, *,
    max_results: int)` and return `list[SearchResult]`.
    """

    name: ClassVar[str] = "web_search"
    description: ClassVar[str] = (
        "Search the web for the given query. Returns a list of "
        "{title, url, snippet} hits as JSON-serialisable dicts."
    )
    input_schema: ClassVar[type[BaseModel]] = _WebSearchInput
    capabilities: ClassVar[frozenset[str]] = frozenset({"network"})

    def __init__(
        self,
        *,
        search_fn: SearchFn | None = None,
        timeout_s: float = _DEFAULT_TIMEOUT_S,
    ) -> None:
        if timeout_s <= 0:
            msg = f"timeout_s must be > 0, got {timeout_s}"
            raise ValueError(msg)
        self._search_fn: SearchFn = search_fn or _duckduckgo_search
        self._timeout_s = timeout_s

    async def run(self, **kwargs: Any) -> list[dict[str, str]]:
        query: str = kwargs["query"]
        max_results: int = kwargs.get("max_results", _DEFAULT_MAX_RESULTS)
        try:
            results = await asyncio.wait_for(
                self._search_fn(query, max_results=max_results),
                timeout=self._timeout_s,
            )
        except TimeoutError:
            msg = f"web_search: backend exceeded timeout_s={self._timeout_s}"
            raise TimeoutError(msg) from None
        # Serialise to JSON-friendly dicts; keeps the LLM contract
        # simple (no Pydantic model in the tool's return value).
        return [r.model_dump() for r in results]


# ----------------------------------------------------------------------
# Default backend — DuckDuckGo HTML scrape
# ----------------------------------------------------------------------


async def _duckduckgo_search(
    query: str, *, max_results: int = _DEFAULT_MAX_RESULTS
) -> list[SearchResult]:
    """Default search backend — DuckDuckGo's HTML page scrape.

    Fragile by design (DuckDuckGo can change its HTML at any time).
    Emits a warning log if it falls over so operators can swap to a
    real backend (Serper, Tavily, Brave).
    """
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
    request = Request(  # noqa: S310 — explicit https URL with constant scheme
        url, headers={"User-Agent": _DEFAULT_USER_AGENT}
    )
    loop = asyncio.get_running_loop()
    try:
        # urlopen is sync; run in executor to avoid blocking the loop.
        html = await loop.run_in_executor(None, _fetch_text, request)
    except Exception as exc:
        logger.warning(
            "web_search: DuckDuckGo backend failed (%s). "
            "Swap to a real backend (Serper/Tavily/Brave) by passing "
            "search_fn=...",
            exc,
        )
        return []
    return _parse_duckduckgo_html(html, max_results=max_results)


def _fetch_text(request: Request) -> str:
    # The Request URL is constructed in `_duckduckgo_search` with a
    # constant `https://html.duckduckgo.com/...` prefix; it is never
    # derived from caller input. Bandit B310's "audit url open for
    # permitted schemes" warning doesn't apply.
    with urlopen(request, timeout=_DEFAULT_TIMEOUT_S) as resp:  # noqa: S310  # nosec B310
        body: bytes = resp.read()
    return body.decode("utf-8", errors="replace")


# Match DuckDuckGo HTML result blocks: <a class="result__a" href="...">title</a>
# followed by <a class="result__snippet">snippet</a>. The href is a
# DuckDuckGo redirect that wraps the real URL in a `uddg=` param.
_RESULT_RE = re.compile(
    r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>'
    r'.*?<a[^>]*class="result__snippet"[^>]*>(.*?)</a>',
    re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _parse_duckduckgo_html(html: str, *, max_results: int) -> list[SearchResult]:
    """Extract titles, URLs, and snippets from DuckDuckGo's HTML.

    Returns at most `max_results` hits. Empty list on parse failure.
    """
    out: list[SearchResult] = []
    for match in _RESULT_RE.finditer(html):
        if len(out) >= max_results:
            break
        href, title_html, snippet_html = match.groups()
        url = _unwrap_ddg_redirect(href)
        out.append(
            SearchResult(
                title=_strip_html(title_html).strip(),
                url=url,
                snippet=_strip_html(snippet_html).strip(),
            )
        )
    return out


def _unwrap_ddg_redirect(href: str) -> str:
    """DuckDuckGo wraps result URLs as `/l/?kh=-1&uddg=<encoded>`.
    Pull the real URL back out."""
    if not href.startswith(("/l/", "//duckduckgo.com/l/")):
        return href
    parsed = urlparse(href if href.startswith("//") else f"https:{href}")
    qs = parse_qs(parsed.query)
    raw = qs.get("uddg", [""])[0]
    return unquote(raw) or href


def _strip_html(s: str) -> str:
    return _TAG_RE.sub("", s)


# Default instance — DuckDuckGo backend, 10s timeout.
web_search = WebSearchTool()


__all__ = ["SearchResult", "WebSearchTool", "web_search"]
