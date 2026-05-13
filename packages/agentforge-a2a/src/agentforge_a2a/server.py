"""`A2AServer` — exposes an `Agent` over the A2A wire format
(feat-014).

FastAPI app with three endpoints:

- `POST /a2a/v1/calls` — invoke a whitelisted endpoint
  synchronously and return one `A2AResponse`.
- `POST /a2a/v1/calls/stream` — invoke a whitelisted endpoint
  and emit a Server-Sent-Events stream of `A2AChunk` frames
  (v0.2 follow-up).
- `GET /a2a/v1/info` — return the endpoint catalogue +
  framework version.

Lifecycle:

  1. Bearer auth via the canonical `AuthPolicy` (feat-014
     chunk 1).
  2. Endpoint name validated against the whitelist (404
     otherwise; on the stream endpoint we instead emit a
     single ``kind="error"`` frame and close the stream so
     the contract stays "always SSE" once authenticated).
  3. `X-AgentForge-Run-Id` (if present) is recorded on the
     response as `parent_run_id` for the cross-framework chain.
  4. `X-AgentForge-Budget-Usd` (if present + valid) caps the
     inner `Agent.run`'s budget.
  5. The supplied `task_builder` callable converts the payload
     into the task string the `Agent` receives.
  6. Findings on the result are serialised through
     `agentforge.recording._finding_payload` so the wire
     shape stays tolerant of any `Finding` Protocol-compatible
     object.

Streaming (v0.3) drives `Agent.stream(task)` and forwards each
`StreamingEvent` emitted by the strategy as one `A2AChunk` SSE
frame. The strategy's terminal `done` event is swallowed; the
server emits its own canonical `done` chunk carrying
`output` + `cost_usd` + `run_id`. The v0.2 transient
`agent._on_step` hook dance is gone — events arrive
pre-typed from the strategy generator.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any

import uvicorn
from agentforge.agent import Agent
from agentforge.recording import _finding_payload
from agentforge_core.contracts.auth import AuthPolicy
from agentforge_core.observability.tracing import get_tracer
from agentforge_core.production.budget import BudgetPolicy
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from opentelemetry.trace.propagation.tracecontext import (
    TraceContextTextMapPropagator,
)
from pydantic import BaseModel, ConfigDict

from agentforge_a2a._runner import A2AServerRunner
from agentforge_a2a.values import (
    A2AChunk,
    A2AEndpointConfig,
    A2AEndpointDescriptor,
    A2APeerInfo,
    A2AResponse,
)

_log = logging.getLogger("agentforge_a2a.server")
_VERSION = "0.1"
"""A2A wire-format version we ship — bumped when the request/
response shape changes."""

TaskBuilder = Callable[[str, dict[str, Any]], str]
"""Maps (endpoint_name, payload) -> the task string the agent
receives. Default: JSON-encode the payload."""


def _default_task_builder(endpoint: str, payload: dict[str, Any]) -> str:
    """Concatenates endpoint name + JSON payload for the agent."""
    body = json.dumps(payload, sort_keys=True)
    return f"a2a.{endpoint}: {body}"


def _sse_frame(chunk: A2AChunk) -> bytes:
    """Encode one `A2AChunk` as a single SSE `data:` frame."""
    return b"data: " + chunk.model_dump_json().encode("utf-8") + b"\n\n"


class CallRequest(BaseModel):
    """Body of `POST /a2a/v1/calls`."""

    model_config = ConfigDict(extra="forbid")

    endpoint: str
    payload: dict[str, Any]
    budget_usd: float | None = None


class A2AServer:
    """FastAPI app exposing an `Agent` as an A2A peer."""

    def __init__(
        self,
        agent: Agent,
        *,
        auth: AuthPolicy,
        endpoints: list[str],
        task_builder: TaskBuilder | None = None,
        host: str = "0.0.0.0",  # noqa: S104  # nosec B104
        port: int = 8080,
        runner: A2AServerRunner | None = None,
        endpoint_descriptors: list[A2AEndpointConfig] | None = None,
        server_name: str = "agentforge",
    ) -> None:
        self._agent = agent
        self._auth = auth
        self._endpoints = list(endpoints)
        self._task_builder = task_builder or _default_task_builder
        self._host = host
        self._port = port
        self._runner = runner
        self._endpoint_descriptors = list(endpoint_descriptors or [])
        self._server_name = server_name
        self.app = self._build_app()

    @property
    def endpoints(self) -> tuple[str, ...]:
        return tuple(self._endpoints)

    def _build_app(self) -> FastAPI:
        app = FastAPI(title="agentforge-a2a")
        bearer = HTTPBearer(auto_error=False)

        async def require_principal(
            credentials: HTTPAuthorizationCredentials | None = Depends(bearer),  # noqa: B008
        ) -> Any:
            token = credentials.credentials if credentials is not None else None
            principal = await self._auth.authenticate(token)
            if principal is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
            return principal

        @app.get("/a2a/v1/info")
        async def info(_p: Any = Depends(require_principal)) -> dict[str, Any]:  # noqa: B008
            return self._build_info().model_dump(mode="json")

        @app.post("/a2a/v1/calls")
        async def call(
            body: CallRequest,
            request: Request,
            _p: Any = Depends(require_principal),  # noqa: B008
        ) -> dict[str, Any]:
            return await self._handle_call(body, request)

        @app.post("/a2a/v1/calls/stream")
        async def stream_call(
            body: CallRequest,
            request: Request,
            _p: Any = Depends(require_principal),  # noqa: B008
        ) -> StreamingResponse:
            return StreamingResponse(
                self._stream_call(body, request),
                media_type="text/event-stream",
            )

        return app

    def _build_info(self) -> A2APeerInfo:
        """Render the discovery payload returned by `/a2a/v1/info`."""
        by_name = {d.name: d for d in self._endpoint_descriptors}
        descriptors = [
            A2AEndpointDescriptor(
                name=name,
                description=(by_name[name].description if name in by_name else ""),
                input_schema=(dict(by_name[name].accepts) if name in by_name else {}),
            )
            for name in self._endpoints
        ]
        return A2APeerInfo(
            version=_VERSION,
            server_name=self._server_name,
            endpoints=descriptors,
        )

    async def _handle_call(self, body: CallRequest, request: Request) -> dict[str, Any]:
        if body.endpoint not in self._endpoints:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"unknown endpoint: {body.endpoint!r}",
            )
        parent_run_id = request.headers.get("X-AgentForge-Run-Id")
        # feat-009 v0.3 polish: W3C TraceContext propagation. Extract
        # the caller's span context from `traceparent` (no-op when
        # missing) and use it as the parent for the inner work so the
        # `a2a.call` span — and its child `agent.run` — stitches into
        # the caller's trace.
        extracted_ctx = TraceContextTextMapPropagator().extract(dict(request.headers))
        tracer = get_tracer()
        with tracer.start_as_current_span(
            "a2a.call",
            context=extracted_ctx,
            attributes={
                "agentforge.a2a.endpoint": body.endpoint,
                "agentforge.a2a.parent_run_id": parent_run_id or "",
            },
        ):
            result = await self._run_with_budget_cap(body, request)
        response = A2AResponse(
            output=result.output,
            findings=tuple(_finding_payload(f) for f in getattr(result, "findings", ())),
            cost_usd=result.cost_usd,
            run_id=result.run_id,
            parent_run_id=parent_run_id,
        )
        body_dict: dict[str, Any] = json.loads(response.model_dump_json())
        return body_dict

    async def _stream_call(self, body: CallRequest, request: Request) -> AsyncIterator[bytes]:
        """SSE generator for `POST /a2a/v1/calls/stream`.

        Drives `Agent.stream(task)` and forwards each
        ``StreamingEvent`` as one ``A2AChunk`` ``data:`` frame.
        The strategy's terminal ``done`` event is swallowed; this
        method emits the canonical ``done`` chunk carrying
        ``output`` + ``cost_usd`` + ``run_id``. Strategy errors
        surface as a terminal ``kind="error"`` frame.
        """
        parent_run_id = request.headers.get("X-AgentForge-Run-Id")
        if body.endpoint not in self._endpoints:
            yield _sse_frame(
                A2AChunk(
                    kind="error",
                    content={
                        "error": "unknown_endpoint",
                        "message": f"unknown endpoint: {body.endpoint!r}",
                    },
                    parent_run_id=parent_run_id,
                )
            )
            return

        # feat-009 v0.3 polish: W3C TraceContext propagation.
        extracted_ctx = TraceContextTextMapPropagator().extract(dict(request.headers))
        tracer = get_tracer()
        a2a_span_cm = tracer.start_as_current_span(
            "a2a.call",
            context=extracted_ctx,
            attributes={
                "agentforge.a2a.endpoint": body.endpoint,
                "agentforge.a2a.parent_run_id": parent_run_id or "",
                "agentforge.a2a.streaming": True,
            },
        )

        task_str = self._task_builder(body.endpoint, body.payload)
        budget_cap = self._read_budget_header(request)
        original_budget = self._agent._budget
        if budget_cap is not None:
            self._agent._budget = BudgetPolicy(
                usd=min(original_budget.usd, budget_cap),
                max_tokens=original_budget.max_tokens,
                max_iterations=original_budget.max_iterations,
                error_streak_limit=original_budget.error_streak_limit,
            )

        done_content: dict[str, Any] | None = None
        a2a_span_cm.__enter__()
        try:
            async for event in self._agent.stream(task_str):
                if event.kind == "done":
                    raw = event.content if isinstance(event.content, dict) else {}
                    done_content = {
                        "output": _coerce_jsonable(raw.get("output")),
                        "cost_usd": float(raw.get("cost_usd", 0.0) or 0.0),
                        "run_id": str(raw.get("run_id", "")),
                    }
                    continue
                yield _sse_frame(
                    A2AChunk(
                        kind=event.kind,
                        content=event.content,
                        metadata=dict(event.metadata),
                        parent_run_id=parent_run_id,
                    )
                )
        except Exception as exc:
            yield _sse_frame(
                A2AChunk(
                    kind="error",
                    content={
                        "error": type(exc).__name__,
                        "message": str(exc),
                    },
                    parent_run_id=parent_run_id,
                )
            )
            return
        finally:
            if budget_cap is not None:
                self._agent._budget = original_budget
            a2a_span_cm.__exit__(None, None, None)

        final = done_content or {"output": None, "cost_usd": 0.0, "run_id": ""}
        yield _sse_frame(
            A2AChunk(
                kind="done",
                content=final,
                run_id=final["run_id"] or None,
                parent_run_id=parent_run_id,
            )
        )

    async def _run_with_budget_cap(self, body: CallRequest, request: Request) -> Any:
        """Run the agent honouring the per-call ``X-AgentForge-Budget-Usd``
        header. Restores the original budget on the way out."""
        budget_cap = self._read_budget_header(request)
        task = self._task_builder(body.endpoint, body.payload)
        if budget_cap is None:
            return await self._agent.run(task)
        original_budget = self._agent._budget
        self._agent._budget = BudgetPolicy(
            usd=min(original_budget.usd, budget_cap),
            max_tokens=original_budget.max_tokens,
            max_iterations=original_budget.max_iterations,
            error_streak_limit=original_budget.error_streak_limit,
        )
        try:
            return await self._agent.run(task)
        finally:
            self._agent._budget = original_budget

    @staticmethod
    def _read_budget_header(request: Request) -> float | None:
        raw = request.headers.get("X-AgentForge-Budget-Usd")
        if raw is None or not raw:
            return None
        try:
            value = float(raw)
        except ValueError:
            _log.warning("invalid X-AgentForge-Budget-Usd header: %r", raw)
            return None
        if value < 0:
            return None
        return value

    async def serve(self) -> None:
        """Run the server until interrupted. Uses the injected
        runner when present, else falls back to a real uvicorn
        server."""
        if self._runner is not None:
            await self._runner.serve()
            return
        config = uvicorn.Config(self.app, host=self._host, port=self._port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.stop()


def _coerce_jsonable(value: Any) -> Any:
    """Best-effort JSON-friendly coercion for the streamed
    ``done`` content. Strings / numbers / bools / None / dicts /
    lists pass through; everything else becomes ``str(value)``."""
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _coerce_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [_coerce_jsonable(v) for v in value]
    return str(value)


__all__ = [
    "A2AServer",
    "CallRequest",
    "TaskBuilder",
]
