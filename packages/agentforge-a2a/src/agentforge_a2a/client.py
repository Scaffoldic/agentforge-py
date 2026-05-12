"""A2A client (feat-014).

`agent_call(target, payload, ...)` resolves a `<peer>:<endpoint>`
target against the configured peers and dispatches an HTTP POST
through the peer's `A2AClientRunner`. The caller's current
`RunContext` is propagated via `X-AgentForge-Run-Id` so the
callee can record it as `parent_run_id` (feat-007).

Budget propagation: when the caller binds an
`agentforge.cli._build`-style budget to the current run, the
proposed `budget_usd` reserves against it before the call;
`commit(actual)` + `release_reservation(budget_usd)` fires on
success; `release_reservation(budget_usd)` on failure. v0.4
threads the budget via the optional `budget` kwarg — the helper
stays callable from contexts without a bound budget too.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agentforge_core.production.budget import BudgetPolicy
from agentforge_core.production.exceptions import (
    A2AAuthError,
    A2ACallError,
    A2ATimeout,
    ModuleError,
)
from agentforge_core.production.run_context import current_run

from agentforge_a2a._runner import A2AClientRunner
from agentforge_a2a.auth import ClientAuth, build_outgoing_auth
from agentforge_a2a.values import A2APeerConfig, A2AResponse

HTTP_UNAUTHORIZED = 401
HTTP_FORBIDDEN = 403


@dataclass
class A2APeer:
    """One configured A2A peer + its outgoing-auth + runner."""

    name: str
    url: str
    auth: ClientAuth
    runner: A2AClientRunner

    @classmethod
    def from_config(
        cls,
        config: dict[str, Any] | A2APeerConfig,
        *,
        runner: A2AClientRunner,
    ) -> A2APeer:
        pc = config if isinstance(config, A2APeerConfig) else A2APeerConfig.model_validate(config)
        return cls(
            name=pc.name,
            url=pc.url,
            auth=build_outgoing_auth(pc.auth),
            runner=runner,
        )


async def agent_call(
    target: str,
    payload: dict[str, Any],
    *,
    peers: dict[str, A2APeer],
    timeout_s: float = 60.0,
    budget_usd: float | None = None,
    budget: BudgetPolicy | None = None,
) -> A2AResponse:
    """Invoke a remote A2A peer.

    Args:
        target: ``"<peer>:<endpoint>"``. ``<peer>`` resolves
            against the ``peers`` map.
        payload: Endpoint-specific JSON body.
        peers: Map of peer name → `A2APeer`.
        timeout_s: Per-call timeout in seconds.
        budget_usd: Proposed budget the callee should respect.
        budget: Optional `BudgetPolicy` the call reserves against
            (caller-side accounting). When None, the helper does
            no reserve/commit dance — useful for fire-and-forget
            calls.

    Returns:
        Parsed `A2AResponse`.

    Raises:
        A2AAuthError: peer rejected credentials.
        A2ATimeout: call exceeded ``timeout_s``.
        A2ACallError: any other transport / protocol failure.
    """
    peer_name, endpoint = _parse_target(target)
    peer = peers.get(peer_name)
    if peer is None:
        raise ModuleError(f"unknown a2a peer: {peer_name!r}")

    headers = _build_headers(peer.auth, budget_usd)
    body = {"endpoint": endpoint, "payload": payload, "budget_usd": budget_usd}

    if budget is not None and budget_usd is not None:
        budget.reserve(budget_usd)
    try:
        try:
            raw = await peer.runner.post(
                peer.url,
                headers=headers,
                json=body,
                ssl_context=peer.auth.ssl_context,
                timeout_s=timeout_s,
            )
        except TimeoutError as exc:
            # Python 3.11+ aliases asyncio.TimeoutError to the
            # builtin TimeoutError; a single except clause catches
            # both.
            raise A2ATimeout(f"a2a call to {peer_name!r} exceeded {timeout_s:.1f}s") from exc
        except Exception as exc:
            raise A2ACallError(f"a2a call to {peer_name!r} failed: {exc}") from exc

        _raise_for_error_body(peer_name, raw)
        response = A2AResponse.model_validate(raw)
    except BaseException:
        if budget is not None and budget_usd is not None:
            budget.release_reservation(budget_usd)
        raise
    else:
        if budget is not None and budget_usd is not None:
            budget.commit(response.cost_usd)
            budget.release_reservation(budget_usd)
    return response


def _parse_target(target: str) -> tuple[str, str]:
    if ":" not in target:
        raise ModuleError(f"a2a target must be '<peer>:<endpoint>', got {target!r}")
    peer_name, endpoint = target.split(":", 1)
    if not peer_name or not endpoint:
        raise ModuleError(f"a2a target must be '<peer>:<endpoint>', got {target!r}")
    return peer_name, endpoint


def _build_headers(auth: ClientAuth, budget_usd: float | None) -> dict[str, str]:
    headers: dict[str, str] = {"Content-Type": "application/json"}
    headers.update(auth.headers)
    try:
        ctx = current_run()
    except RuntimeError:
        ctx = None
    if ctx is not None:
        headers["X-AgentForge-Run-Id"] = ctx.run_id
    if budget_usd is not None:
        headers["X-AgentForge-Budget-Usd"] = f"{budget_usd:.6f}"
    return headers


def _raise_for_error_body(peer_name: str, raw: dict[str, Any]) -> None:
    """Map an error-shaped body to the right A2A* exception."""
    if "error" not in raw:
        return
    code = raw.get("error", "")
    message = raw.get("message", "")
    status = int(raw.get("status", 0)) if isinstance(raw.get("status"), (int, str)) else 0
    if status in (HTTP_UNAUTHORIZED, HTTP_FORBIDDEN) or code in ("unauthorized", "forbidden"):
        raise A2AAuthError(f"a2a peer {peer_name!r} rejected credentials: {message}")
    raise A2ACallError(f"a2a peer {peer_name!r} returned error {code!r}: {message}")


__all__ = [
    "A2APeer",
    "agent_call",
]
