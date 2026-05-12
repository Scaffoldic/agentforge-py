"""Live integration tests for `agentforge-mcp` (feat-013 v0.2).

Tests in this directory are gated by `@pytest.mark.live` and
skipped by the default pre-commit + CI runs (which use
`pytest -m "not live"`). Run them with:

    uv run pytest -m live packages/agentforge-mcp/tests/integration/
"""
