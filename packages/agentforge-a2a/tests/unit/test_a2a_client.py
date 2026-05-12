"""Unit tests for `agent_call` + auth helpers (feat-014 chunk 3)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest
from agentforge_a2a import (
    A2APeer,
    A2APeerConfig,
    BearerAuth,
    MutualTLSAuth,
    agent_call,
    build_outgoing_auth,
)
from agentforge_a2a._inmem_runner import FakeA2AClientRunner
from agentforge_core.production.budget import BudgetPolicy
from agentforge_core.production.exceptions import (
    A2AAuthError,
    A2ACallError,
    A2ATimeout,
    BudgetExceeded,
    ModuleError,
)
from agentforge_core.production.run_context import bind_run, new_run, reset_run


def _make_peer(
    name: str = "fact-checker",
    runner: FakeA2AClientRunner | None = None,
    auth: dict | None = None,
) -> A2APeer:
    runner = runner if runner is not None else FakeA2AClientRunner()
    config = A2APeerConfig(
        name=name,
        url=f"https://internal.{name}.example/a2a",
        auth=auth if auth is not None else {"type": "bearer", "token": "tok"},
    )
    return A2APeer.from_config(config, runner=runner)


def test_bearer_auth_builds_header() -> None:
    auth = BearerAuth("abc")
    assert auth.headers == {"Authorization": "Bearer abc"}
    assert auth.ssl_context is None


def test_build_outgoing_auth_supports_bearer() -> None:
    auth = build_outgoing_auth({"type": "bearer", "token": "x"})
    assert auth.headers["Authorization"] == "Bearer x"


def test_build_outgoing_auth_rejects_empty_bearer_token() -> None:
    with pytest.raises(ModuleError, match="non-empty 'token'"):
        build_outgoing_auth({"type": "bearer", "token": ""})


def test_build_outgoing_auth_rejects_unknown_type() -> None:
    with pytest.raises(ModuleError, match="unknown a2a auth type"):
        build_outgoing_auth({"type": "magic", "token": "x"})


def test_build_outgoing_auth_empty_means_no_auth() -> None:
    auth = build_outgoing_auth({})
    assert auth.headers == {}
    assert auth.ssl_context is None


def test_mutual_tls_auth_builds_ssl_context(tmp_path: Path) -> None:
    cert, key = _write_self_signed_cert(tmp_path)
    auth = MutualTLSAuth(cert_path=cert, key_path=key)
    assert auth.headers == {}
    assert auth.ssl_context is not None


def test_build_outgoing_auth_mtls_requires_both_paths() -> None:
    with pytest.raises(ModuleError, match="requires both 'cert' and 'key'"):
        build_outgoing_auth({"type": "mtls", "cert": "/x"})


@pytest.mark.asyncio
async def test_agent_call_happy_path() -> None:
    runner = FakeA2AClientRunner.with_response(
        {"output": "verified", "run_id": "callee-run", "cost_usd": 0.05}
    )
    peer = _make_peer(runner=runner)
    result = await agent_call(
        "fact-checker:verify",
        {"claim": "x"},
        peers={"fact-checker": peer},
    )
    assert result.output == "verified"
    assert result.cost_usd == pytest.approx(0.05)
    assert len(runner.calls) == 1
    assert runner.calls[0].headers["Authorization"] == "Bearer tok"
    assert runner.calls[0].json["endpoint"] == "verify"
    assert runner.calls[0].json["payload"] == {"claim": "x"}


@pytest.mark.asyncio
async def test_agent_call_unknown_peer_raises_module_error() -> None:
    with pytest.raises(ModuleError, match="unknown a2a peer"):
        await agent_call("missing:x", {}, peers={})


@pytest.mark.asyncio
async def test_agent_call_bad_target_format_raises() -> None:
    with pytest.raises(ModuleError, match="'<peer>:<endpoint>'"):
        await agent_call("noformat", {}, peers={"any": _make_peer()})


@pytest.mark.asyncio
async def test_agent_call_translates_401_to_auth_error() -> None:
    runner = FakeA2AClientRunner.with_response(
        {"error": "unauthorized", "message": "bad token", "status": 401}
    )
    peer = _make_peer(runner=runner)
    with pytest.raises(A2AAuthError, match="rejected credentials"):
        await agent_call("fact-checker:x", {}, peers={"fact-checker": peer})


@pytest.mark.asyncio
async def test_agent_call_translates_generic_error_body() -> None:
    runner = FakeA2AClientRunner.with_response({"error": "bad_request", "message": "no payload"})
    peer = _make_peer(runner=runner)
    with pytest.raises(A2ACallError, match="bad_request"):
        await agent_call("fact-checker:x", {}, peers={"fact-checker": peer})


@pytest.mark.asyncio
async def test_agent_call_translates_timeout() -> None:
    runner = FakeA2AClientRunner()
    runner.set_error(TimeoutError())
    peer = _make_peer(runner=runner)
    with pytest.raises(A2ATimeout, match="exceeded"):
        await agent_call("fact-checker:x", {}, peers={"fact-checker": peer})


@pytest.mark.asyncio
async def test_agent_call_translates_runtime_error_to_call_error() -> None:
    runner = FakeA2AClientRunner()
    runner.set_error(RuntimeError("connection reset"))
    peer = _make_peer(runner=runner)
    with pytest.raises(A2ACallError, match="connection reset"):
        await agent_call("fact-checker:x", {}, peers={"fact-checker": peer})


@pytest.mark.asyncio
async def test_budget_reserve_commits_on_success() -> None:
    runner = FakeA2AClientRunner.with_response({"output": "ok", "run_id": "r1", "cost_usd": 0.10})
    peer = _make_peer(runner=runner)
    budget = BudgetPolicy(usd=1.0)
    await agent_call(
        "fact-checker:x",
        {},
        peers={"fact-checker": peer},
        budget_usd=0.25,
        budget=budget,
    )
    assert budget.spent_usd == pytest.approx(0.10)
    assert budget.reserved_usd == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_budget_releases_on_failure() -> None:
    runner = FakeA2AClientRunner()
    runner.set_error(RuntimeError("boom"))
    peer = _make_peer(runner=runner)
    budget = BudgetPolicy(usd=1.0)
    with pytest.raises(A2ACallError):
        await agent_call(
            "fact-checker:x",
            {},
            peers={"fact-checker": peer},
            budget_usd=0.25,
            budget=budget,
        )
    assert budget.spent_usd == 0.0
    assert budget.reserved_usd == 0.0


@pytest.mark.asyncio
async def test_budget_exceeded_blocks_call() -> None:
    runner = FakeA2AClientRunner.with_response({"output": "ok", "run_id": "r1", "cost_usd": 0.0})
    peer = _make_peer(runner=runner)
    budget = BudgetPolicy(usd=0.10)
    with pytest.raises(BudgetExceeded):
        await agent_call(
            "fact-checker:x",
            {},
            peers={"fact-checker": peer},
            budget_usd=1.0,
            budget=budget,
        )
    # No call should have gone out — reservation blew up first.
    assert len(runner.calls) == 0


@pytest.mark.asyncio
async def test_runid_header_propagated_when_run_context_bound() -> None:
    runner = FakeA2AClientRunner.with_response({"output": "ok", "run_id": "r"})
    peer = _make_peer(runner=runner)
    ctx = new_run(task="caller-task")
    token = bind_run(ctx)
    try:
        await agent_call("fact-checker:x", {}, peers={"fact-checker": peer})
    finally:
        reset_run(token)
    assert runner.calls[0].headers["X-AgentForge-Run-Id"] == ctx.run_id


@pytest.mark.asyncio
async def test_budget_header_propagated() -> None:
    runner = FakeA2AClientRunner.with_response({"output": "ok", "run_id": "r"})
    peer = _make_peer(runner=runner)
    await agent_call(
        "fact-checker:x",
        {},
        peers={"fact-checker": peer},
        budget_usd=0.5,
    )
    assert runner.calls[0].headers["X-AgentForge-Budget-Usd"].startswith("0.5")


def _write_self_signed_cert(tmp: Path) -> tuple[Path, Path]:
    """Generate a fresh self-signed cert+key pair via openssl.

    Avoids hardcoding PEM blobs (LibreSSL vs OpenSSL parse the
    same blob differently on macOS vs Linux) by shelling out to
    the system's openssl binary at test time.
    """
    binary = shutil.which("openssl")
    if binary is None:
        pytest.skip("openssl binary not available")

    cert = tmp / "cert.pem"
    key = tmp / "key.pem"
    subprocess.run(  # nosec B603 — fully-qualified binary, fixed args
        [
            binary,
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-keyout",
            str(key),
            "-out",
            str(cert),
            "-days",
            "1",
            "-nodes",
            "-subj",
            "/CN=localhost",
        ],
        check=True,
        capture_output=True,
    )
    return cert, key
