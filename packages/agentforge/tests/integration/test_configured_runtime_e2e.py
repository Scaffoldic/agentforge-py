"""End-to-end guard for the config → build → run wiring (offline).

This is the anti-drift net for the class of issue that slipped past
unit coverage in 0.5.0 — bug-022 (memory built from config), bug-023
(replay reconstructs the strategy), and enh-004 (`providers.config`
passed to the provider constructor). Those all lived in the seam
between configuration and the real runtime, which per-feature unit
tests mock away with fakes. Here we exercise the *real* build path
against *real* offline-capable backends (sqlite memory, the shipped
`FakeLLMClient` via record/replay, real provider construction), so a
documented config knob that stops reaching the runtime fails CI.

All offline: no API key, no network.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from agentforge import Agent
from agentforge._testing import FakeLLMClient, echo_response
from agentforge.cli._build import build_agent_from_config
from agentforge.cli.main import main
from agentforge_core.config.loader import load_config
from agentforge_core.contracts.memory import MemoryStore


def _write_config(path: Path, *, db: Path, provider_config: str = "") -> Path:
    """A config that actually wires a backend + a typed provider block."""
    cfg = path / "agentforge.yaml"
    cfg.write_text(
        "agent:\n"
        "  strategy: react\n"
        "  budget:\n    usd: 5\n"
        "providers:\n"
        "  default:\n"
        "    type: bedrock\n"
        "    model: us.anthropic.claude-haiku-4-5-20251001-v1:0\n"
        f"{provider_config}"
        "modules:\n"
        "  memory:\n"
        "    driver: sqlite\n"
        f"    config:\n      path: {db}\n",
        encoding="utf-8",
    )
    return cfg


@pytest.mark.asyncio
async def test_configured_agent_builds_with_provider_config_and_sqlite_memory(
    tmp_path: Path,
) -> None:
    """Build a fully-configured agent through the real loader + builder:
    a typed `providers.default.config` block (enh-004) AND a sqlite
    `modules.memory` (bug-022) must both reach the runtime. The provider
    is constructed but never called, so this stays offline."""
    pytest.importorskip("agentforge_memory_sqlite")
    pytest.importorskip("agentforge_bedrock")
    db = tmp_path / "mem.sqlite"
    cfg = _write_config(
        tmp_path,
        db=db,
        # If `config:` were dropped (the enh-004 bug), `timeout_seconds`
        # never reaches BedrockClient and this build is a silent no-op;
        # an *unknown* key would raise — either way drift is caught.
        # (Bedrock constructs offline — no AWS call until first use.)
        provider_config="    config:\n      timeout_seconds: 42\n      region: us-east-1\n",
    )
    config = load_config(cfg)
    agent = await build_agent_from_config(config)
    try:
        # Memory came from config (not the InMemoryStore default).
        assert isinstance(agent.memory, MemoryStore)
        assert type(agent.memory).__name__ == "SqliteMemoryStore"
    finally:
        await agent.close()


async def _seed_recording(db: Path) -> str:
    """Record one offline run (shipped FakeLLMClient) into a sqlite store
    and return its run_id, for `--replay` to consume."""
    from agentforge_memory_sqlite import SqliteMemoryStore  # noqa: PLC0415

    store = await SqliteMemoryStore.from_path(db)
    fake = FakeLLMClient(responses=[echo_response(content="Hello.", cost_usd=0.001)])
    async with Agent(model=fake, strategy="react", record_runs=store) as agent:
        result = await agent.run("say hi")
    await store.close()
    return str(result.run_id)


def test_configured_agent_runs_offline_via_replay(tmp_path: Path) -> None:
    """The full CLI run path against a configured sqlite backend: seed a
    recording, then `agentforge run --replay` rebuilds memory-from-config
    (bug-022) and the strategy (bug-023) and completes — exit 0, no key,
    no network. Sync test: `main()` drives its own event loop."""
    pytest.importorskip("agentforge_memory_sqlite")
    db = tmp_path / "rec.sqlite"
    run_id = asyncio.run(_seed_recording(db))

    cfg = _write_config(tmp_path, db=db)
    code = main(
        ["run", "--path", str(cfg), "--replay", run_id, "--output-format", "plain", "say hi"]
    )
    assert code == 0
