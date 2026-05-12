"""`A2ABridge` — orchestrates A2A clients + an optional server
(feat-014).

Loaded by feat-010's resolver from
`modules.protocols[a2a].config:`. Mirrors `MCPBridge`'s shape:

- `from_config(config_dict, *, agent, auth, client_runner,
  server_runner)` builds peers + an optional server from a
  validated `A2AConfig`.
- `peers` is a dict of `{name -> A2APeer}` ready for
  `agent_call(...)`.
- `server` is an `A2AServer | None`; when present, `start()`
  schedules it as an asyncio task and `close()` cancels.
"""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any, ClassVar

from agentforge.agent import Agent
from agentforge_core.contracts.auth import AuthPolicy

from agentforge_a2a._runner import A2AClientRunner, A2AServerRunner
from agentforge_a2a.client import A2APeer, discover_peer
from agentforge_a2a.config import A2AConfig
from agentforge_a2a.server import A2AServer
from agentforge_a2a.values import A2APeerInfo


class A2ABridge:
    """Top-level orchestrator for a2a clients + server.

    The bridge does NOT own the `Agent` instance — callers pass
    it explicitly when they want a server side. Without an
    agent, `from_config` builds the client side only (peers
    available; `server is None`).
    """

    config_schema: ClassVar[type[A2AConfig]] = A2AConfig
    """Picked up by feat-012's `validate_module_configs` so
    `agentforge config validate` enforces the A2A schema."""

    def __init__(
        self,
        *,
        peers: dict[str, A2APeer],
        server: A2AServer | None = None,
    ) -> None:
        self._peers = dict(peers)
        self._server = server
        self._serve_task: asyncio.Task[None] | None = None
        self._peer_info: dict[str, A2APeerInfo] = {}

    @property
    def peers(self) -> dict[str, A2APeer]:
        return dict(self._peers)

    @property
    def server(self) -> A2AServer | None:
        return self._server

    @property
    def peer_info(self) -> dict[str, A2APeerInfo]:
        """Cached `A2APeerInfo` keyed by peer name (populated by
        `discover_all()` — empty until then)."""
        return dict(self._peer_info)

    @classmethod
    def from_config(
        cls,
        config: dict[str, Any],
        *,
        agent: Agent | None = None,
        auth: AuthPolicy | None = None,
        client_runner: A2AClientRunner,
        server_runner: A2AServerRunner | None = None,
    ) -> A2ABridge:
        """Build a bridge from a validated A2A config dict.

        Args:
            config: Raw ``{peers: [...], expose: {...}}`` dict.
                The chunk-5 schema (`A2AConfig`) validates this.
            agent: Required when ``config.expose.enabled`` is
                True. The server side wraps it.
            auth: Required when ``config.expose.enabled`` is
                True. The server validates incoming bearers
                against this policy.
            client_runner: Shared `A2AClientRunner` for all
                peers. Pass a `FakeA2AClientRunner` in tests.
            server_runner: Optional `A2AServerRunner` injected
                into the server's lifecycle.
        """
        validated = A2AConfig.model_validate(config)
        peers = {pc.name: A2APeer.from_config(pc, runner=client_runner) for pc in validated.peers}
        server: A2AServer | None = None
        if validated.expose is not None and validated.expose.enabled:
            if agent is None or auth is None:
                msg = (
                    "A2A expose.enabled=True requires both an Agent and an "
                    "AuthPolicy to be supplied to A2ABridge.from_config."
                )
                raise ValueError(msg)
            server = A2AServer(
                agent=agent,
                auth=auth,
                endpoints=[e.name for e in validated.expose.endpoints],
                endpoint_descriptors=list(validated.expose.endpoints),
                host=validated.expose.host,
                port=validated.expose.port,
                runner=server_runner,
            )
        return cls(peers=peers, server=server)

    async def discover_all(self, *, timeout_s: float = 10.0) -> dict[str, A2APeerInfo]:
        """Probe every configured peer's `/a2a/v1/info` endpoint
        and cache the result on `self.peer_info`.

        Re-callable — replaces the cached entry per peer. Caller-
        driven: never invoked automatically by `start()`.
        """
        fresh: dict[str, A2APeerInfo] = {}
        for name, peer in self._peers.items():
            fresh[name] = await discover_peer(peer, timeout_s=timeout_s)
        self._peer_info = fresh
        return dict(self._peer_info)

    async def start(self) -> None:
        """Launch the server (if any) in the background. Idempotent."""
        if self._server is None or self._serve_task is not None:
            return
        self._serve_task = asyncio.create_task(self._server.serve())

    async def close(self) -> None:
        """Stop the server (if running) and drain peers."""
        if self._server is not None:
            await self._server.stop()
        if self._serve_task is not None and not self._serve_task.done():
            self._serve_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._serve_task
            self._serve_task = None
        for peer in self._peers.values():
            await peer.runner.close()


__all__ = ["A2ABridge"]
