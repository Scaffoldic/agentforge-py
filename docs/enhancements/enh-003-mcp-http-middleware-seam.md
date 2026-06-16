# enh-003: MCP HTTP transport middleware seam

> Improves a *shipped* feature (feat-013, MCP — specifically the
> [enh-001](./enh-001-mcp-http-server-transport.md) HTTP transport). Filed
> as issue #93 by a consumer agent building on agentforge-py 0.2.4. Not a
> defect — the HTTP transport works as designed — this adds a missing
> extension seam so an agent can put auth (or any ASGI middleware) in
> front of the transport without re-implementing the serve path.

---

## Metadata

| Field | Value |
|---|---|
| **ID** | enh-003 |
| **Title** | `middleware=` seam on `MCPServer.from_http` |
| **Status** | `shipped` (0.5.0) |
| **Owner** | kjoshi |
| **Created** | 2026-06-16 |
| **Target version** | 0.5.0 |
| **Languages** | `python` |
| **Improves** | feat-013 (MCP) / enh-001 (HTTP transport) |

---

## 1. Summary

Let `MCPServer.from_http(...)` accept a list of Starlette `Middleware`
applied to the streamable-HTTP app the default runner builds — the seam
for a bearer-token gate, rate limiting, or CORS in front of an otherwise
open transport.

## 2. Motivation

`MCPServer.from_http(...)` builds the Starlette app
(`StreamableHTTPSessionManager` mounted at `/mcp`) and serves it under
uvicorn **inside a private method** (`_SDKServerRunner._serve_http`). There
was **no seam to add ASGI/Starlette middleware**: no `middleware=` / `auth=`
parameter, and the built `app` wasn't exposed. The only injection point was
`from_http(..., runner=…)`, which forces a consumer to re-implement the
whole HTTP serve path (the `list_tools` / `call_tool` dispatch +
`StreamableHTTPSessionManager` + uvicorn, ~40 lines) purely to wrap the app
in auth.

The streamable-HTTP server is otherwise wide open on any exposed port. A
framework that pitches "production rails" shouldn't make the only path to a
bearer-token gate "fork the framework's serve loop." The **A2A** transport
already ships a first-class auth story (`agentforge_a2a/auth.py` —
`BearerAuth` / mTLS / `build_outgoing_auth`); MCP HTTP had no equivalent.

## 2.5 Framework-level vs derived-agent-level

**Framework.** The HTTP serve path — the Starlette app construction, the
`StreamableHTTPSessionManager` wiring, the uvicorn server — is framework
code inside a private method. A consumer cannot wrap it in middleware
without reconstructing it.

- **Derived-agent test:** the workaround (a custom `MCPServerRunner` that
  duplicates the framework's HTTP wiring just to wrap the app) re-implements
  internals the framework owns and tracks them across versions — fails the
  test → framework work.
- **How it helps derived agents:** a consumer adds auth (or rate-limit /
  CORS / logging) with `from_http(..., middleware=[Middleware(MyAuth, …)])`
  and keeps the entire serve path on the framework's default runner —
  no duplication, no internals to track.

## 3. Before / after

| Aspect | Before | After |
|---|---|---|
| Add auth to HTTP MCP | fork the serve path via a custom `runner` (~40 lines) | `from_http(..., middleware=[...])` |
| Built Starlette app | private, not exposed | wrapped with caller middleware |
| Default no-auth path | unchanged | unchanged (`middleware=None`) |

```python
# after — a bearer-token gate in front of the transport
from starlette.middleware import Middleware

server = MCPServer.from_http(
    tools=tools,
    host=host,
    port=port,
    middleware=[Middleware(BearerAuthMiddleware, token=os.environ["MCP_TOKEN"])],
)
await server.serve()
```

## 4. Backward compatibility

Additive. `middleware` defaults to `None` → identical to today's behaviour.
Ignored when a custom `runner` is supplied (the runner owns its own app).
No change for stdio transport or existing agents.

## 5. Implementation

`from_http` gains a `middleware: Sequence[Any] | None` parameter, threaded
to `_build_http_server_runner(..., middleware=…)` → `_SDKServerRunner` →
`_serve_http`. The app construction was split into a module-level
`_build_http_app(asgi_handler, *, lifespan, middleware)` helper that mounts
the `/mcp` ASGI route and passes `middleware` to `Starlette(...)`. Splitting
it out makes the seam unit-testable without the `mcp` SDK or a live uvicorn
server. The param is typed `Sequence[Any]` so the public API doesn't force a
top-level `starlette` import (it stays lazy, as the rest of the serve path
already is).

## 6. Test plan

- Unit (shipped): `test_build_http_app_applies_caller_middleware_as_auth_gate`
  builds the app with a bearer-auth `BaseHTTPMiddleware`, then uses Starlette
  `TestClient` to assert `401` without the token and `200` (route reached)
  with it; `test_build_http_app_without_middleware_reaches_route` asserts the
  open default. No live server / mcp SDK needed.
- Covered by the existing `@pytest.mark.live` `test_mcp_live.py` round-trip
  for the end-to-end serve path.

## 7. Risks

| Risk | Mitigation |
|---|---|
| Middleware type couples API to Starlette | Typed `Sequence[Any]`; starlette stays a lazy import (already a transitive `mcp` dep) |
| Custom `runner` + `middleware` both passed | `middleware` is documented as ignored when a `runner` is supplied |

## 8. References

- Improved feature: feat-013 (MCP), enh-001 (HTTP transport)
- Issue: #93
- Precedent: `agentforge_a2a/auth.py` (A2A bearer / mTLS auth)
