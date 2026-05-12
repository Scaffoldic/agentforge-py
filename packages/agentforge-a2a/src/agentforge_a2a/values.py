"""A2A value types (feat-014).

Wire-format-shaped Pydantic models that ride between the client
(`agent_call`) and the server (`A2AServer`). All frozen — values
are immutable once built.

`A2AResponse` mirrors spec §4.2. The three config models
(`A2APeerConfig`, `A2AEndpointConfig`, `A2AExposeConfig`) feed
the YAML side via `A2AConfig`.

v0.2 follow-up adds the discovery + streaming wire shapes:

- `A2AEndpointDescriptor` + `A2APeerInfo` — the rich shape
  returned by `GET /a2a/v1/info` and consumed by
  `discover_peer(...)`.
- `A2AChunk` + `A2AChunkKind` — the streaming wire format
  emitted by `POST /a2a/v1/calls/stream`.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

A2AChunkKind = Literal["step", "tool_call", "tool_result", "done", "error"]
"""Kinds of frames streamed over `POST /a2a/v1/calls/stream`.

- ``step`` — generic agent step (think + others).
- ``tool_call`` — agent invoked a tool.
- ``tool_result`` — observation from a tool call.
- ``done`` — terminal frame carrying the final output + cost.
- ``error`` — terminal error frame.
"""


class A2AResponse(BaseModel):
    """Response returned by `agent_call(...)` and built by
    `A2AServer.POST /a2a/v1/calls`."""

    model_config = ConfigDict(frozen=True, strict=True)

    output: Any
    findings: tuple[dict[str, Any], ...] = ()
    cost_usd: float = Field(default=0.0, ge=0.0)
    run_id: str
    parent_run_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2APeerConfig(BaseModel):
    """One entry under `modules.protocols[a2a].config.peers:`.

    `auth` is a free-form dict: `{type: bearer, token: ...}` or
    `{type: mtls, cert: ..., key: ...}` — interpreted by
    `agentforge_a2a.auth.build_outgoing_auth`.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(min_length=1)
    url: str = Field(min_length=1)
    auth: dict[str, Any] = Field(default_factory=dict)


class A2AEndpointConfig(BaseModel):
    """One entry under `modules.protocols[a2a].config.expose.endpoints:`."""

    model_config = ConfigDict(strict=True, extra="forbid")

    name: str = Field(min_length=1)
    description: str = ""
    accepts: dict[str, Any] = Field(default_factory=dict)


class A2AExposeConfig(BaseModel):
    """`modules.protocols[a2a].config.expose:` — server-side
    configuration when this agent acts as an A2A peer."""

    model_config = ConfigDict(strict=True, extra="forbid")

    enabled: bool = True
    host: str = "0.0.0.0"  # noqa: S104  # nosec B104 — caller binds explicitly in prod
    port: int = 8080
    auth: dict[str, Any] = Field(default_factory=dict)
    endpoints: list[A2AEndpointConfig] = Field(default_factory=list)


class A2AEndpointDescriptor(BaseModel):
    """One endpoint advertised by `GET /a2a/v1/info`."""

    model_config = ConfigDict(frozen=True, strict=True)

    name: str = Field(min_length=1)
    description: str = ""
    input_schema: dict[str, Any] = Field(default_factory=dict)


class A2APeerInfo(BaseModel):
    """Discovery payload returned by `GET /a2a/v1/info`."""

    model_config = ConfigDict(frozen=True, strict=True)

    version: str
    server_name: str = ""
    endpoints: list[A2AEndpointDescriptor] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class A2AChunk(BaseModel):
    """One frame on the streaming `/a2a/v1/calls/stream` channel."""

    model_config = ConfigDict(frozen=True, strict=True)

    kind: A2AChunkKind
    content: dict[str, Any] | str | None = None
    step: dict[str, Any] | None = None
    run_id: str | None = None
    parent_run_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "A2AChunk",
    "A2AChunkKind",
    "A2AEndpointConfig",
    "A2AEndpointDescriptor",
    "A2AExposeConfig",
    "A2APeerConfig",
    "A2APeerInfo",
    "A2AResponse",
]
