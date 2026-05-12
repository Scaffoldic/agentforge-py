"""`A2AServer` — exposes an `Agent` over the A2A wire format
(feat-014).

FastAPI app with two endpoints:

- `POST /a2a/v1/calls` — invoke a whitelisted endpoint.
- `GET /a2a/v1/info` — return the endpoint catalogue +
  framework version.

Lifecycle:

  1. Bearer auth via the canonical `AuthPolicy` (feat-014
     chunk 1).
  2. Endpoint name validated against the whitelist (404
     otherwise).
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
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from typing import Any

import uvicorn
from agentforge.agent import Agent
from agentforge.recording import _finding_payload
from agentforge_core.contracts.auth import AuthPolicy
from agentforge_core.production.budget import BudgetPolicy
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from agentforge_a2a._runner import A2AServerRunner
from agentforge_a2a.values import (
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
        budget_cap = self._read_budget_header(request)
        if budget_cap is not None:
            # Apply the cap by temporarily lowering the agent's
            # budget for this run. We restore after.
            original_budget = self._agent._budget
            self._agent._budget = BudgetPolicy(
                usd=min(original_budget.usd, budget_cap),
                max_tokens=original_budget.max_tokens,
                max_iterations=original_budget.max_iterations,
                error_streak_limit=original_budget.error_streak_limit,
            )
            try:
                result = await self._agent.run(self._task_builder(body.endpoint, body.payload))
            finally:
                self._agent._budget = original_budget
        else:
            result = await self._agent.run(self._task_builder(body.endpoint, body.payload))

        response = A2AResponse(
            output=result.output,
            findings=tuple(_finding_payload(f) for f in getattr(result, "findings", ())),
            cost_usd=result.cost_usd,
            run_id=result.run_id,
            parent_run_id=parent_run_id,
        )
        body_dict: dict[str, Any] = json.loads(response.model_dump_json())
        return body_dict

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


__all__ = [
    "A2AServer",
    "CallRequest",
    "TaskBuilder",
]
