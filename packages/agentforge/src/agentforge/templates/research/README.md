# {{ project_name }}

{{ description }} Open-ended research with citations. Uses the
Plan-Execute strategy + web_search to break a complex question
into sub-tasks, then synthesises a `NarrativeFinding`.

```bash
uv sync
cp .env.example .env
uv run {{ project_slug }} "what changed in claude-sonnet 4.5 vs 4.7?"
```

Defaults to `web_search` (DuckDuckGo HTML scrape). Replace with a
serper / tavily backend by passing `search_fn=` to `WebSearchTool`.
