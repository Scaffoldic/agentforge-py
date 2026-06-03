"""`ChatServer` — FastAPI app exposing `ChatSession` over HTTP.

REST API (per feat-020 §4.1):

    POST   /sessions                    -> 200 + {id}
    GET    /sessions                    -> 200 + [SessionInfo]
    DELETE /sessions/{id}               -> 204
    POST   /sessions/{id}/messages      -> 200 + ChatResponse (JSON)
                                           or SSE when Accept matches
    GET    /sessions/{id}/messages      -> 200 + [ChatTurn]
    WS     /sessions/{id}/ws            -> bidirectional streaming
    GET    /healthz                     -> 200

v0.2 ships an in-process bearer-auth policy + token-bucket
rate limiting. Postgres / Redis history drivers are deferred to
v0.3 follow-up PRs; today the server runs against any
`ChatHistoryStore` instance (in-memory or sqlite).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import time
import uuid
from collections.abc import Callable
from typing import Any

import uvicorn
from agentforge.agent import Agent
from agentforge_chat import ChatSession
from agentforge_core.contracts.chat import ChatHistoryStore, HistoryTruncationStrategy
from agentforge_core.values.chat import ChatChunk, ChatResponse, ChatTurn
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Request,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, ConfigDict

from agentforge_chat_http.auth import BearerAuthPolicy, Principal


class SendMessageRequest(BaseModel):
    """Body of POST /sessions/{id}/messages."""

    model_config = ConfigDict(extra="forbid")

    content: str
    idempotency_key: str | None = None


class CreateSessionRequest(BaseModel):
    """Body of POST /sessions."""

    model_config = ConfigDict(extra="forbid")

    session_id: str | None = None
    system_prompt: str | None = None


class _RateLimiter:
    """Naive in-process token bucket per (owner, session)."""

    def __init__(self, *, per_minute: int) -> None:
        self._per_minute = max(1, per_minute)
        self._counts: dict[tuple[str, str], list[float]] = {}

    def check(self, owner: str, session_id: str) -> bool:
        key = (owner, session_id)
        now = time.monotonic()
        window = self._counts.setdefault(key, [])
        # purge entries older than 60s
        cutoff = now - 60.0
        while window and window[0] < cutoff:
            window.pop(0)
        if len(window) >= self._per_minute:
            return False
        window.append(now)
        return True


class ChatServer:
    """FastAPI app wrapper holding session state."""

    def __init__(
        self,
        *,
        agent_factory: Callable[[], Agent],
        history_store: ChatHistoryStore,
        auth: BearerAuthPolicy,
        host: str = "0.0.0.0",  # noqa: S104  # nosec B104 — server defaults to all interfaces; caller binds explicitly in prod
        port: int = 8080,
        cors_origins: list[str] | None = None,
        rate_limit_per_session_per_minute: int = 60,
        truncation: HistoryTruncationStrategy | None = None,
    ) -> None:
        self._agent_factory = agent_factory
        self._history = history_store
        self._auth = auth
        self._host = host
        self._port = port
        self._cors_origins = list(cors_origins or [])
        self._truncation = truncation
        self._sessions: dict[str, ChatSession] = {}
        self._session_owners: dict[str, str] = {}
        self._sessions_lock = asyncio.Lock()
        self._rate_limit = _RateLimiter(per_minute=rate_limit_per_session_per_minute)
        self.app = self._build_app()

    @property
    def http_app(self) -> FastAPI:
        return self.app

    def _build_app(self) -> FastAPI:
        app = FastAPI(title="agentforge-chat-http")
        if self._cors_origins:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=self._cors_origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        bearer = HTTPBearer(auto_error=False)

        async def require_principal(
            credentials: HTTPAuthorizationCredentials | None = Depends(bearer),  # noqa: B008 — FastAPI Depends idiom
        ) -> Principal:
            token = credentials.credentials if credentials is not None else None
            principal = await self._auth.authenticate(token)
            if principal is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
            return principal

        @app.get("/healthz")
        async def healthz() -> dict[str, str]:
            return {"status": "ok"}

        @app.post("/sessions")
        async def create_session(
            body: CreateSessionRequest,
            principal: Principal = Depends(require_principal),  # noqa: B008
        ) -> dict[str, str]:
            session = await self._create_session(body, principal)
            return {"id": session.session_id}

        @app.get("/sessions")
        async def list_sessions(
            principal: Principal = Depends(require_principal),  # noqa: B008
        ) -> list[dict[str, Any]]:
            infos = await self._history.list_sessions(owner=principal.id)
            return [json.loads(i.model_dump_json()) for i in infos]

        @app.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
        async def delete_session(
            session_id: str,
            principal: Principal = Depends(require_principal),  # noqa: B008
        ) -> None:
            self._assert_owner(session_id, principal)
            async with self._sessions_lock:
                session = self._sessions.pop(session_id, None)
                self._session_owners.pop(session_id, None)
            if session is not None:
                await session.close()
            await self._history.delete_session(session_id)

        @app.post("/sessions/{session_id}/messages")
        async def post_message(
            session_id: str,
            body: SendMessageRequest,
            request: Request,
            principal: Principal = Depends(require_principal),  # noqa: B008
        ) -> Any:
            self._assert_owner(session_id, principal)
            if not self._rate_limit.check(principal.id, session_id):
                raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS)
            session = await self._get_session(session_id, principal)
            accept = request.headers.get("accept", "")
            if "text/event-stream" in accept:
                return StreamingResponse(
                    self._sse_stream(session, body),
                    media_type="text/event-stream",
                )
            response = await session.send(body.content, idempotency_key=body.idempotency_key)
            return json.loads(response.model_dump_json())

        @app.get("/sessions/{session_id}/messages")
        async def get_history(
            session_id: str,
            principal: Principal = Depends(require_principal),  # noqa: B008
            limit: int | None = None,
        ) -> list[dict[str, Any]]:
            self._assert_owner(session_id, principal)
            turns = await self._history.load(session_id, limit=limit)
            return [json.loads(t.model_dump_json()) for t in turns]

        @app.websocket("/sessions/{session_id}/ws")
        async def ws_endpoint(ws: WebSocket, session_id: str) -> None:
            await self._ws_endpoint(ws, session_id)

        return app

    async def _ws_endpoint(self, ws: WebSocket, session_id: str) -> None:
        await ws.accept()
        token = ws.headers.get("authorization", "").removeprefix("Bearer ").strip()
        principal = await self._auth.authenticate(token or None)
        if principal is None:
            await ws.close(code=4401)
            return
        try:
            self._assert_owner(session_id, principal)
        except HTTPException:
            await ws.close(code=4403)
            return
        session = await self._get_session(session_id, principal)
        try:
            while True:
                raw = await ws.receive_text()
                payload = json.loads(raw)
                message = str(payload["content"])
                cancellation = asyncio.Event()
                consumer = asyncio.create_task(
                    self._consume_stream(ws, session, message, cancellation)
                )
                receiver = asyncio.create_task(ws.receive_text())
                _, pending = await asyncio.wait(
                    {consumer, receiver},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if not consumer.done():
                    cancellation.set()
                for task in pending:
                    task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await task
        except WebSocketDisconnect:
            return

    async def _consume_stream(
        self,
        ws: WebSocket,
        session: ChatSession,
        message: str,
        cancellation: asyncio.Event,
    ) -> None:
        async for chunk in await session.stream(message, cancellation=cancellation):
            await ws.send_text(chunk.model_dump_json())

    async def _sse_stream(
        self,
        session: ChatSession,
        body: SendMessageRequest,
    ) -> Any:
        async for chunk in await session.stream(body.content, idempotency_key=body.idempotency_key):
            yield self._sse_format(chunk)

    def _sse_format(self, chunk: ChatChunk) -> bytes:
        return f"data: {chunk.model_dump_json()}\n\n".encode()

    async def _create_session(
        self, body: CreateSessionRequest, principal: Principal
    ) -> ChatSession:
        agent = self._agent_factory()
        session = ChatSession(
            agent=agent,
            session_id=body.session_id or uuid.uuid4().hex,
            history_store=self._history,
            system_prompt=body.system_prompt,
            owner=principal.id,
            truncation=self._truncation,
        )
        async with self._sessions_lock:
            self._sessions[session.session_id] = session
            self._session_owners[session.session_id] = principal.id
        # Create the session row up front so list_sessions filtering works
        # before the first turn (bug-018). create_session upserts via the
        # store, so this is safe on a fresh process / SQLite driver.
        await self._history.create_session(session.session_id, owner=principal.id)
        return session

    async def _get_session(self, session_id: str, principal: Principal) -> ChatSession:
        async with self._sessions_lock:
            cached = self._sessions.get(session_id)
        if cached is not None:
            return cached
        # Cold path: rehydrate a session object from existing history.
        agent = self._agent_factory()
        session = ChatSession(
            agent=agent,
            session_id=session_id,
            history_store=self._history,
            owner=principal.id,
            truncation=self._truncation,
        )
        async with self._sessions_lock:
            self._sessions[session_id] = session
            self._session_owners[session_id] = principal.id
        return session

    def _assert_owner(self, session_id: str, principal: Principal) -> None:
        recorded = self._session_owners.get(session_id)
        if recorded is not None and recorded != principal.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    async def serve(self) -> None:
        config = uvicorn.Config(self.app, host=self._host, port=self._port, log_level="info")
        server = uvicorn.Server(config)
        await server.serve()


__all__ = [
    "ChatResponse",
    "ChatServer",
    "ChatTurn",
    "CreateSessionRequest",
    "SendMessageRequest",
]
