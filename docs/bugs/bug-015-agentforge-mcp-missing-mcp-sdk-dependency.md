---
status: fixed in 0.2.4
severity: P2
found-in: v0.2.3
found-via: live integration of a Bedrock-backed MCP agent (Khemchand Joshi, 2026-05-27)
---

# bug-015 — `agentforge-py[mcp]` does not pull the `mcp` SDK (broken extra chain)

> **Root cause corrected after source verification (2026-06-02).** The
> original title ("`agentforge-mcp` does not declare the `mcp` SDK")
> is **wrong**: `agentforge-mcp` *does* declare it — as the optional
> `[mcp]` extra (`packages/agentforge-mcp/pyproject.toml:38`,
> `mcp = ["mcp>=1.0,<2"]`), behind lazy imports by deliberate design (the
> standard vendor-SDK lazy-import pattern; fakes inject runners in tests).
> The real defect is the **meta-package extra chain** — see Root cause.

## Symptom

After `pip install agentforge-py[mcp]` or `pip install agentforge-mcp`,
calling `MCPServerClient.from_stdio(...)` raises:

```
agentforge_core.production.exceptions.ModuleError:
  mcp SDK is not installed. Install via `pip install mcp` to consume MCP servers.
```

The user followed runbook 09 to the letter; the install completed
successfully; the framework's own `agentforge_mcp/client.py:137` does:

```python
from mcp import ClientSession  # ModuleNotFoundError: No module named 'mcp'
```

## Reproduction

```bash
uv venv .venv --python 3.13
uv pip install "agentforge-py[mcp]"
.venv/bin/python -c "from agentforge_mcp import MCPServerClient; import asyncio; \
  asyncio.run(MCPServerClient.from_stdio(name='x', command='cat'))"
# → ModuleError: mcp SDK is not installed
```

## Root cause

The `mcp` SDK *is* declared, but as an extra on the leaf package
(`agentforge-mcp[mcp]`). The meta-package's own `mcp` extra does **not**
chain it:

```toml
# packages/agentforge/pyproject.toml:105
mcp = ["agentforge-mcp ~= 0.2.4"]          # ← pulls the package, NOT its [mcp] extra
```

So `pip install agentforge-py[mcp]` installs `agentforge-mcp` *without*
its `[mcp]` extra, the upstream `mcp` SDK never lands, and the lazy
import in `client.py:137` raises the friendly `ModuleError` at runtime.
The error message itself points at `pip install mcp` rather than the
canonical `agentforge-mcp[mcp]`, compounding the confusion. (There is no
"runbook 09"; docs are `feat-NNN` specs.)

## Fix proposal

One-line fix in the meta package — chain the extra so the SDK installs
with the documented one-liner:

```toml
# packages/agentforge/pyproject.toml
mcp = ["agentforge-mcp[mcp] ~= 0.2.4"]
```

Also update the `ModuleError` text in `_build_stdio_runner` /
`client.py` to recommend `pip install "agentforge-mcp[mcp]"` (or
`agentforge-py[mcp]` once chained) instead of bare `pip install mcp`.
Do **not** make `mcp` a hard dependency of `agentforge-mcp` — the lazy
optional-extra design is intentional and lets the test suite inject fake
runners without the SDK.

## Workaround

Consumers install `agentforge-mcp[mcp]` explicitly (or add `mcp >= 1.0`
to their own `pyproject.toml`). a downstream consumer ships this with a
comment pointing at this bug.

## Framework-level vs derived-agent-level

**Framework (packaging).** The framework *documents* and *advertises*
the `agentforge-py[mcp]` install path, so the framework owns making that
path actually deliver a working MCP runtime.

- **Derived-agent test:** a consumer can work around it in one line, but
  they shouldn't have to discover that the framework's own advertised
  extra is incomplete. The fix lives in framework `pyproject.toml`, not
  consumer code → framework defect.
- **How the fix helps derived agents:** `pip install
  "agentforge-py[mcp]"` works as documented — the plug-and-play install
  promise holds instead of failing at first MCP call.

## Notes

- The friendly `ModuleError` is good and should stay — only its
  suggested command needs updating to `agentforge-mcp[mcp]`.
- **Audit the other vendor-SDK modules** for the same broken-chain
  pattern: any meta-package extra of the form `X = ["agentforge-X ~= ..."]`
  that should be `["agentforge-X[vendor] ~= ..."]`. Candidates with
  optional SDK extras: `agentforge-langfuse`, `agentforge-phoenix`,
  `agentforge-a2a`, etc. Worth a one-pass sweep during the fix.

## Resolution (v0.2.4)

Audited all 34 packages (`pyproject.toml` deps + optional-dependencies).
Every vendor SDK is an optional extra on its leaf package — **none** are
hard-bundled — so the meta comment claiming "ollama / litellm bundle
their SDK as a hard dep" was wrong. Three defect classes fixed in
`packages/agentforge/pyproject.toml` (individual extras **and** `[all]`):

1. **Missing chain (12 extras, the reported bug class)** — `ollama`,
   `litellm`, `voyage`, `mcp`, `langfuse`, `phoenix`, `statsd`,
   `evidently`, `reranker-cohere`, `reranker-voyage`,
   `reranker-mixedbread`, `reranker-sentence-transformers`. Each now
   chains `agentforge-<pkg>[<sdk>]`. (`anthropic` / `openai` were
   already correct.) `[all]` previously installed *zero* vendor SDKs;
   now chains them too.
2. **Phantom extra** — `bedrock` requested `agentforge-bedrock[bedrock]`,
   but bedrock has no such extra (its SDK `aioboto3`/`botocore` is a
   hard dep). Now bare `agentforge-bedrock`.
3. **Eager-import-as-optional** — `agentforge-chat` imports
   `SqliteChatHistory` (→ `import aiosqlite`) at package import, yet
   declared `aiosqlite` as an optional `[sqlite]` extra, so
   `import agentforge_chat` failed on a bare install. `aiosqlite` is now
   a hard dependency (matching sibling `agentforge-memory-sqlite`); the
   `[sqlite]` extra, chat README, and manifest comment were updated.

Also: the `mcp` `ModuleError` text (4 sites in `agentforge-mcp`) now
recommends `agentforge-mcp[mcp]` instead of bare `pip install mcp`.

A generic regression test (`packages/agentforge/tests/unit/test_extras_chain.py`)
parses every sister `pyproject.toml` and asserts each meta extra chains
exactly the leaf package's extras — catching both missing and phantom
extras for current and future packages.

**Out of scope (noted, not fixed here):** `agentforge-chat`'s
token-budget truncation lazily imports `tiktoken` / `anthropic` for
tokenisation; these are genuinely-optional advanced-feature deps with no
advertised meta extra, so they are not part of this broken-chain fix.
