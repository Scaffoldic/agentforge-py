"""`ProtocolBridge` — the runtime contract for `modules.protocols`
handlers (feat-013).

A protocol handler turns a `modules.protocols[*]` config block into a
set of `Tool`s the agent can call, and owns the lifecycle of whatever
connections back that (subprocesses, sockets, sessions). The runtime
(`build_agent_from_config`) resolves each entry's name under the
``protocols`` resolver category, builds the handler from its config,
`start()`s it, merges `tools` into the `Agent`, and `close()`s it on
`Agent.close()`.

The contract is a `@runtime_checkable` `Protocol` rather than an ABC so
handlers in optional packages (`agentforge-mcp`'s `MCPBridge`, a future
`agentforge-a2a` bridge) satisfy it structurally — `agentforge` /
`agentforge-core` never import the handler packages.

Expected construction shape (duck-typed, not part of the Protocol since
classmethods don't express cleanly here): a classmethod
``from_config(config: dict) -> ProtocolBridge`` that is **pure data** —
it must not open transports or drive an event loop (do that in
``start()``), so it is safe to call from within a running loop.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from agentforge_core.contracts.tool import Tool


@runtime_checkable
class ProtocolBridge(Protocol):
    """Lifecycle + tool-source contract for a protocols handler."""

    @property
    def tools(self) -> list[Tool]:
        """The tools this bridge contributes, populated by `start()`."""
        ...

    async def start(self) -> None:
        """Open connections and populate `tools`. Safe to call inside a
        running event loop."""
        ...

    async def close(self) -> None:
        """Tear down every connection this bridge opened."""
        ...


__all__ = ["ProtocolBridge"]
