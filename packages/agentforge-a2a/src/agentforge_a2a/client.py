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

from collections.abc import AsyncIterator
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
from agentforge_a2a.values import A2AChunk, A2APeerConfig, A2APeerInfo, A2AResponse

_CALLS_SUFFIX = "/calls"
_INFO_PATH = "/info"
_STREAM_PATH = "/calls/stream"

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


async def agent_call_stream(
    target: str,
    payload: dict[str, Any],
    *,
    peers: dict[str, A2APeer],
    timeout_s: float = 60.0,
    budget_usd: float | None = None,
    budget: BudgetPolicy | None = None,
) -> AsyncIterator[A2AChunk]:
    """Streaming counterpart to `agent_call`.

    Opens an SSE channel against ``peer.url + "/stream"`` (the
    stream endpoint is derived from the unary calls URL) and
    yields each `A2AChunk` frame as it arrives. The terminal
    ``kind="done"`` frame commits actual cost against the
    supplied ``budget``; ``kind="error"`` releases the
    reservation and raises the matching A2A* exception.
    """
    peer_name, endpoint = _parse_target(target)
    peer = peers.get(peer_name)
    if peer is None:
        raise ModuleError(f"unknown a2a peer: {peer_name!r}")

    headers = _build_headers(peer.auth, budget_usd)
    body = {"endpoint": endpoint, "payload": payload, "budget_usd": budget_usd}
    stream_url = _stream_url_from_calls_url(peer.url)

    if budget is not None and budget_usd is not None:
        budget.reserve(budget_usd)

    try:
        stream = peer.runner.post_stream(
            stream_url,
            headers=headers,
            json=body,
            ssl_context=peer.auth.ssl_context,
            timeout_s=timeout_s,
        )
        async for raw in _wrap_stream_errors(peer_name, timeout_s, stream):
            chunk = A2AChunk.model_validate(raw)
            if chunk.kind == "error":
                _raise_for_error_chunk(peer_name, chunk)
            if chunk.kind == "done" and budget is not None:
                content = chunk.content if isinstance(chunk.content, dict) else {}
                budget.commit(float(content.get("cost_usd", 0.0)))
            yield chunk
    finally:
        if budget is not None and budget_usd is not None:
            budget.release_reservation(budget_usd)


async def _wrap_stream_errors(
    peer_name: str,
    timeout_s: float,
    stream: AsyncIterator[dict[str, Any]],
) -> AsyncIterator[dict[str, Any]]:
    """Yield from ``stream`` while mapping transport errors to A2A*."""
    try:
        async for raw in stream:
            yield raw
    except (A2AAuthError, A2ACallError, A2ATimeout):
        raise
    except TimeoutError as exc:
        raise A2ATimeout(f"a2a stream to {peer_name!r} exceeded {timeout_s:.1f}s") from exc
    except Exception as exc:
        raise A2ACallError(f"a2a stream to {peer_name!r} failed: {exc}") from exc


def _raise_for_error_chunk(peer_name: str, chunk: A2AChunk) -> None:
    content = chunk.content if isinstance(chunk.content, dict) else {}
    code = str(content.get("error", "")) if content else ""
    message = str(content.get("message", "")) if content else ""
    if code in ("unauthorized", "forbidden", "A2AAuthError"):
        raise A2AAuthError(f"a2a peer {peer_name!r} rejected credentials: {message}")
    raise A2ACallError(f"a2a peer {peer_name!r} streamed error {code!r}: {message}")


def _stream_url_from_calls_url(calls_url: str) -> str:
    if calls_url.endswith(_CALLS_SUFFIX):
        return calls_url + "/stream"
    head, sep, _ = calls_url.rpartition(_CALLS_SUFFIX)
    if sep:
        return head + _STREAM_PATH
    return calls_url.rstrip("/") + _STREAM_PATH


async def discover_peer(
    peer: A2APeer,
    *,
    timeout_s: float = 10.0,
) -> A2APeerInfo:
    """Probe ``peer``'s ``GET /a2a/v1/info`` endpoint and return
    the parsed `A2APeerInfo`.

    `peer.url` is the unary calls URL (e.g.
    ``https://x/a2a/v1/calls``); the info URL is derived by
    swapping the trailing ``/calls`` for ``/info`` so callers
    only ever configure one URL per peer.
    """
    info_url = _info_url_from_calls_url(peer.url)
    headers = dict(peer.auth.headers)
    headers.setdefault("Accept", "application/json")
    try:
        raw = await peer.runner.get(
            info_url,
            headers=headers,
            ssl_context=peer.auth.ssl_context,
            timeout_s=timeout_s,
        )
    except (A2AAuthError, A2ACallError, A2ATimeout):
        raise
    except TimeoutError as exc:
        raise A2ATimeout(f"a2a discovery of {peer.name!r} exceeded {timeout_s:.1f}s") from exc
    except Exception as exc:
        raise A2ACallError(f"a2a discovery of {peer.name!r} failed: {exc}") from exc
    _raise_for_error_body(peer.name, raw)
    return A2APeerInfo.model_validate(raw)


def _info_url_from_calls_url(calls_url: str) -> str:
    if calls_url.endswith(_CALLS_SUFFIX):
        return calls_url[: -len(_CALLS_SUFFIX)] + _INFO_PATH
    head, sep, _ = calls_url.rpartition(_CALLS_SUFFIX)
    if sep:
        return head + _INFO_PATH
    return calls_url.rstrip("/") + _INFO_PATH


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
    # feat-009 v0.3 polish: W3C TraceContext propagation. The
    # propagator is a no-op when no active OTel span is bound,
    # so this is safe to call unconditionally.
    _trace_propagator().inject(headers)
    return headers


def _trace_propagator() -> Any:
    """Lazily import OTel's W3C TraceContext propagator.

    Cached at module level via ``_PROPAGATOR_CACHE`` so the import
    only runs once. OpenTelemetry is a required dependency of
    `agentforge-core`, so this import is always safe.
    """
    if _PROPAGATOR_CACHE[0] is None:
        from opentelemetry.trace.propagation.tracecontext import (  # noqa: PLC0415
            TraceContextTextMapPropagator,
        )

        _PROPAGATOR_CACHE[0] = TraceContextTextMapPropagator()
    return _PROPAGATOR_CACHE[0]


_PROPAGATOR_CACHE: list[Any] = [None]


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
    "agent_call_stream",
    "discover_peer",
]
