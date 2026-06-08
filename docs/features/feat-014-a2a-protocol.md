# feat-014: A2A protocol support

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-014 |
| **Title** | Agent-to-Agent (A2A) protocol — cross-framework agent calls |
| **Status** | shipped (Python) |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.1 (contracts + client + server + bridge — shipped); 0.2 (production runner + A2A discovery / registry + bi-directional streaming) |
| **Languages** | both |
| **Module package(s)** | `agentforge-a2a` |
| **Depends on** | feat-001, feat-004, feat-007 (run_id propagation across calls) |
| **Blocks** | none |

---

## 1. Why this feature

Real agent systems are not single agents. A "research assistant" agent calls
a "fact-checker" agent calls a "search" agent. When all three are the same
framework, you can call them as Python functions. When they aren't —
because each team picked a different agent framework while your team uses
AgentForge — you need a protocol.

A2A (Agent-to-Agent) is the emerging standard for cross-framework agent
invocation. It is shipping in major agent toolkits, and adoption is spreading
across the ecosystem. We need to support it to participate in the multi-agent
ecosystem.

The pain without it: every cross-framework integration is a custom REST API,
with custom auth, custom serialisation, custom error semantics. Multiply
that across N team-internal agents and the integration cost explodes.

## 2. Why it must ship as framework

- **Stable contract for cross-team agent calls.** A2A defines the wire
  format; the framework owns the adapter both directions.
- **Run-id propagation across agent boundaries.** When agent A calls agent B,
  B's `run_id` should record A's `run_id` as `parent_run_id` — only the
  framework can do this consistently.
- **Cost accounting through the chain.** Calling another agent costs money.
  The caller's `BudgetPolicy` must reserve cost for the callee.
- **Authentication / capability negotiation** across agents needs a uniform
  story. The framework defines the surface; specific auth backends plug in.
- **Without framework ownership:** every cross-agent call is bespoke; no
  cross-team observability; security wrappers reinvented.

## 3. How derived agents benefit

- **Call another agent like a tool.** `agent_call("fact-checker:check",
  {claim: "..."})` returns a structured response.
- **Expose this agent as an A2A endpoint with one config block.** Other
  frameworks and tools (Claude Desktop, and any A2A-speaking framework) can call it.
- **Cross-agent traces.** A `run_id` chain is visible end-to-end across
  framework boundaries when both ends propagate the A2A header.
- **Budget chain.** Caller's USD cap is honoured by the callee — the callee
  agrees to operate within the cost the caller passes.

## 4. Feature specifications

### 4.1 User-facing experience

Consume another agent:

```yaml
modules:
  protocols:
    - name: a2a
      config:
        peers:
          - name: fact-checker
            url: "https://internal.fact-checker.example/a2a"
            auth: { type: "bearer", token: "${FACT_CHECKER_TOKEN}" }
          - name: search
            url: "https://internal.search.example/a2a"
            auth: { type: "mtls", cert: "...", key: "..." }
```

```python
from agentforge import agent_call

result = await agent_call(
    "fact-checker:verify",
    {"claim": "The capital of Australia is Sydney."},
    timeout_s=30,
)
print(result.output)   # {"verdict": "false", "explanation": "It is Canberra."}
```

Expose this agent:

```yaml
modules:
  protocols:
    - name: a2a
      config:
        expose:
          enabled: true
          host: "0.0.0.0"
          port: 8080
          auth: { type: "bearer", expected_tokens_env: "A2A_TOKENS" }
          endpoints:
            - name: "review-pr"
              description: "Review a pull request and return findings"
              accepts: { pr_url: "string", depth: "shallow|deep" }
```

### 4.2 Public API / contract

```python
# agentforge_a2a/client.py
async def agent_call(
    target: str,                       # "<peer>:<endpoint>"
    payload: dict[str, Any],
    *,
    timeout_s: float = 60,
    budget_usd: float | None = None,    # subdelegate budget
) -> A2AResponse: ...

class A2AResponse(BaseModel):
    output: Any
    findings: list[Finding]
    cost_usd: float
    run_id: str          # callee's run_id
    parent_run_id: str   # caller's run_id

# agentforge_a2a/server.py
class A2AServer:
    """Exposes Agent endpoints over the A2A protocol."""
    def __init__(self, agent: Agent, *, host: str, port: int, auth: AuthPolicy) -> None: ...
    async def serve(self) -> None: ...
    async def stop(self) -> None: ...
```

Wire format follows the A2A specification (JSON over HTTPS, structured
request/response, headers for `run_id`, `parent_run_id`, `budget_usd`,
`auth`).

### 4.3 Internal mechanics

- `agent_call` resolves `<peer>` against `peers` config, builds an HTTPS
  request, propagates `run_id` and `budget_usd` in headers.
- Caller's `BudgetPolicy` reserves the proposed `budget_usd` before the
  call; commits the actual cost on response.
- Server side: incoming request validated, agent run with `parent_run_id`
  bound, response returned with cost.
- Auth backends pluggable: bearer, mTLS, custom (open question 8.1).

### 4.4 Module packaging

`agentforge-a2a`. Depends on the chosen HTTP stack (httpx for client;
uvicorn + Starlette for server in Python; fetch + Hono in TS).

### 4.5 Configuration

See §4.1 examples.

## 5. Plug-and-play & upgrade story

`agentforge add module a2a`. Configuration is YAML. Wire format pinned to
A2A spec version; protocol upgrades go through deprecation cycle.

## 6. Cross-language parity

Both languages ship at v0.4 — A2A spec is language-agnostic, server and
client are straightforward HTTP + JSON.

## 7. Test strategy

- **Round-trip:** agent A calls agent B; both processes; verify response
  shape, `run_id` chain, budget accounting.
- **Auth:** bearer token, mTLS, expired token, missing token — each path
  surfaced with right error code.
- **Cost propagation:** callee's actual cost matches caller's commit.
- **Spec conformance:** validated against published A2A spec test suite.

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| A2A spec is still evolving | Pin to spec version; document supported versions; upgrade module on spec changes |
| Auth backend list will grow | Pluggable `AuthPolicy` ABC; ship `bearer` + `mtls` at v0.4; community can add OAuth/SAML |
| Budget enforcement is advisory across trust boundaries | Document: callee may exceed if compromised; budget is contract within trust domain |
| Server framework choice | Starlette in Python (stable, lightweight); Hono in TS (similar) |
| Should we expose every agent endpoint, or whitelist? | Whitelist via `endpoints:` block in config — explicit |

## 9. Out of scope

- A2A discovery / registry. Out of scope; URLs hard-coded or service-
  discovered by the deployment platform.
- Bi-directional streaming via A2A. Initial version request/response only.
- Implementing alternative inter-agent protocols. A2A is the standard we
  pick; if another standard emerges, separate module.

## 10. Implementation status (Python)

Shipped in PR #27. New Tier-3 sister package
`agentforge-a2a` plus a refactor that lifts feat-020's stub
auth contract into a canonical core ABC.

| Chunk | Commit | What landed |
|---|---|---|
| 1 | `76e2373` | Canonical `agentforge_core.contracts.auth.AuthPolicy` ABC + `Principal` value + `A2ACallError` / `A2AAuthError` / `A2ATimeout` exceptions; `agentforge.auth.EnvBearerAuth` concrete implementation; chat-http `BearerAuthPolicy` aliased to the canonical contract for backward compat. |
| 2 | `b09915b` | New `agentforge-a2a` workspace member: pyproject + manifest.yaml + entry-point under `agentforge.protocols.a2a`. `A2AResponse` / `A2APeerConfig` / `A2AEndpointConfig` / `A2AExposeConfig` value models. `A2AClientRunner` / `A2AServerRunner` Protocols with `# pragma: no cover` production stubs (`_HTTPXClientRunner`, `_UvicornServerRunner`). |
| 3 | `06f4ba6` | `agent_call(target, payload, *, peers, timeout_s, budget_usd, budget)` outgoing client. `BearerAuth` / `MutualTLSAuth` / `build_outgoing_auth` credentials. `FakeA2AClientRunner` / `FakeA2AServerRunner` in `src/_inmem_runner.py` for tests + downstream integration. Run-id + budget propagation via `X-AgentForge-Run-Id` / `X-AgentForge-Budget-Usd` headers. |
| 4 | `4197535` | `A2AServer` FastAPI app — `POST /a2a/v1/calls` + `GET /a2a/v1/info`. Bearer-auth via canonical `AuthPolicy`; endpoint whitelist; parent_run_id propagation; budget cap; findings serialised via `agentforge.recording._finding_payload`. `A2ABridge.from_config(config, *, agent, auth, client_runner, server_runner)` orchestrator with `start()` / `close()` lifecycle. |
| 5 | `f925e0b` | `A2AConfig` Pydantic schema; `A2ABridge.config_schema = A2AConfig` so feat-012's `validate_module_configs` enforces shape on `agentforge config validate`. |
| 6 | (this PR) | Docs + Runbook + roadmap + CHANGELOG + state. |

### Deviations from the design

- **Production wire transport scoped to `# pragma: no cover`.**
  `_HTTPXClientRunner` / `_UvicornServerRunner` raise
  `"Production A2A runner not implemented yet"` until the
  framework's first live integration test against a real A2A
  peer lands. Every unit test injects
  `FakeA2AClientRunner` / `FakeA2AServerRunner` from
  `src/_inmem_runner.py`. Contract surface fully covered.
- **Server framework = FastAPI**, not bare Starlette as the
  spec §4.4 suggests. Matches the existing `chat-http`
  precedent and reuses the same `HTTPBearer` /
  `HTTPException` / `Depends` idioms.
- **Outgoing auth has no policy abstraction.** Per-peer auth
  is dict-driven (`{type: bearer, token: ...}` /
  `{type: mtls, cert: ..., key: ...}`) — matches the spec's
  YAML example. `build_outgoing_auth(config)` is the
  resolution path.
- **`A2AResponse.findings` is `tuple[dict, ...]`**, not
  `tuple[Finding, ...]`. Findings serialise on the wire via
  `_finding_payload(...)` — keeps the wire format JSON-clean
  and tolerant of custom Finding shapes.
- **Budget enforcement is advisory across trust boundaries.**
  `X-AgentForge-Budget-Usd` caps the inner agent's budget on
  the server side; a compromised callee may exceed. Spec §8
  already documents this; the implementation matches.
- **TypeScript port deferred.** Wire format is
  language-neutral.

### Open items

- Real per-token streaming through the strategy ABC (deferred
  to v0.3 alongside feat-020's strategy-level streaming
  follow-up). v0.2 ships step-level streaming.
- A central A2A registry service (out of scope for v0.2 —
  discovery is strictly client-side caching of well-known
  endpoints).
- Per-run hook kwarg on `Agent.run` (cleanup of the streaming
  server's `agent._on_step.append(...)` / remove dance).
- TS port.

### v0.2 follow-up — production runner + discovery + bi-directional streaming

Shipped on the v0.1 → v0.2 line. Closes the three open items
that v0.1 deferred: real HTTP transport, peer discovery, and
streaming. Coverage of the production runner is proven by
`@pytest.mark.live` integration tests (`tests/integration/`),
the framework's second live suite after feat-013.

| Chunk | Commit | What landed |
|---|---|---|
| 1 | `149dbac` | `_HTTPXClientRunner` real body wrapping `httpx.AsyncClient` (lazy allocation; `verify=ssl_context or True`; HTTP 401/403 → `A2AAuthError`, ≥ 400 → `A2ACallError`); `_UvicornServerRunner` real body wrapping `uvicorn.Server` (lazy build in `serve()`; `stop()` sets `should_exit`). `A2AClientRunner` Protocol gains `get(...)` + `post_stream(...) -> AsyncIterator[dict]`. `FakeA2AClientRunner` mirrors the new surface with `set_get_response` / `set_stream` test knobs. Bodies remain `# pragma: no cover` (covered by chunk 6 live tests). |
| 2 | `397999e` | Discovery: `A2APeerInfo` + `A2AEndpointDescriptor` frozen values; `GET /a2a/v1/info` now returns the full rich shape (version, server_name, list-of-descriptors with description + JSON-Schema input shapes); `agentforge_a2a.discover_peer(peer)` probes a peer; `A2ABridge.discover_all()` caches results on `bridge.peer_info`. Info URL is derived from the unary calls URL by swapping `/calls` for `/info` so callers configure only one URL per peer. `A2AServer.__init__` accepts `endpoint_descriptors:` + `server_name:`. |
| 3 | `39cdeaf` | Streaming wire format: `A2AChunk` + `A2AChunkKind` (`step` / `tool_call` / `tool_result` / `done` / `error`). Public re-exports + unit tests against the fake's `responses_stream` knob. |
| 4 | `5aa57bf` | Streaming server: `POST /a2a/v1/calls/stream` returns `text/event-stream` `data: <json>\n\n` frames. Installs a one-off `on_step` hook on the agent for the duration of one call; each `Step` becomes an `A2AChunk` (mapping `think→step`, `act→tool_call`, `observe→tool_result`); a backgrounded `agent.run(...)` task pushes a final `kind="done"` (or `kind="error"`) frame and a sentinel. The 404 path emits a single `kind="error"` chunk so the contract stays "always SSE once authenticated." Unary `/v1/calls` refactored to share the budget-cap path via `_run_with_budget_cap`. |
| 5 | `d633033` | Streaming client: `agent_call_stream(target, payload, *, peers, ...) -> AsyncIterator[A2AChunk]`. Same target / peer / header / budget shape as `agent_call`; commits actual cost on the terminal `done` frame and releases the reservation in `finally`. `kind="error"` frames raise `A2AAuthError` / `A2ACallError` based on the embedded `content.error` code. Transport errors funnel through a `_wrap_stream_errors` helper that maps `TimeoutError → A2ATimeout`. |
| 6 | `10b0d1b` | Live integration tests: `tests/integration/test_a2a_live.py` spins up a real `uvicorn.Server` on a random localhost port, points a real `_HTTPXClientRunner` at it, and round-trips three flows (unary `agent_call`, `discover_peer`, `agent_call_stream`). Helpers (deterministic three-step strategy, `_StaticBearerAuth`, `_spawn_server` async context manager) live in the test file itself — no extra importable module + no `__init__.py` collision with `agentforge-mcp/tests/integration/`. Two small framework adjustments: `A2AResponse` drops `strict=True` (so list↔tuple JSON coercion on `findings` round-trips cleanly), and root `pyproject.toml` ignores `websockets.legacy` / `uvicorn.protocols.websockets` `DeprecationWarning`s (uvicorn imports the legacy module at startup). |
| 7 | `a810583` | New `live` job in `.github/workflows/ci.yml` running `pytest -m live` against every package shipping a `tests/integration/test_*_live.py` suite (mcp + a2a as of v0.2). Runs on every PR + push but does NOT gate merge (`continue-on-error: true`); branch protection stays on the main `test` job. Threshold for adding the job was ≥ 2 packages with live tests. |
| 8 | (this PR) | Docs + Runbook + roadmap + CHANGELOG + state. |

### v0.2 deviations from the v0.1 spec

- **Step-level streaming, not per-token.** The streaming
  endpoint emits one `A2AChunk` per agent `Step` plus a
  terminal `done`. True per-token LLM streaming blocks on
  `ReasoningStrategy.stream()` and lands alongside feat-020's
  strategy-level streaming follow-up in v0.3.
- **`peer.url` semantics unchanged.** `peer.url` is the full
  unary calls URL (`https://x/a2a/v1/calls`); the streaming +
  info URLs are derived by `_stream_url_from_calls_url(...)` /
  `_info_url_from_calls_url(...)`. Callers still configure one
  URL per peer.
- **No central A2A registry server.** Discovery is strictly
  client-side caching via `A2ABridge.discover_all()`.
- **Hook installation on `agent._on_step`.** The streaming
  server appends a one-off hook to the agent's hook list for
  the duration of a single call and removes it in a `finally`
  block. A cleaner per-run-hook surface on `Agent.run` is a
  v0.3 cleanup.
- **`A2AChunkKind` is distinct from `ChatChunkKind`.** A2A
  streams agent-level steps; chat streams text. A
  framework-wide `StreamingChunk` unification is a v0.3 polish.

### Out-of-scope (deferred to v0.3+)

- Real per-token LLM streaming via the strategy ABC.
- Central A2A registry service.
- Per-run hook kwarg on `Agent.run`.
- Unifying `A2AChunkKind` and `ChatChunkKind`.
- Hardening the `live` CI job to gate merge.
- TS port.

### v0.3 follow-up — per-token streaming + chunk-kind unification

Shipped on the v0.1 → v0.3 line. Closes the per-token
streaming + chunk-kind unification items v0.2 deferred. The
per-run hook kwarg on `Agent.run` is **obviated** by the
streaming refactor — the v0.2 hack it would have cleaned up
is gone.

| Chunk | What landed |
|---|---|
| 1 | Framework-wide `StreamingChunkKind` (`text` / `thinking` / `step` / `tool_call` / `tool_result` / `done` / `error`) lives in `agentforge_core.values.chat`. `ChatChunkKind` and `A2AChunkKind` are aliased to it so chat and A2A share one closed vocabulary. The `step` kind stays in the union for strategies that emit step-level events. |
| 2 | `A2AServer._stream_call` drives `Agent.stream(task)` and forwards each `StreamingEvent` as an `A2AChunk` SSE frame. The strategy's terminal `done` is swallowed; the server emits its own canonical `done` with `output` + `cost_usd` + `run_id`. The v0.2 `asyncio.Queue` + backgrounded `_run_agent` + `agent._on_step.append/remove` dance is removed wholesale. Budget-cap swap stays inline. |
| 3 | Live integration test `_PerTokenStrategy` overrides `ReasoningStrategy.stream` to yield three `text` tokens + a `tool_call` + a `tool_result` + a terminal `done`; `test_stream_round_trip` asserts the canonical sequence end-to-end against a real `uvicorn.Server` + `_HTTPXClientRunner`. |
| 4 | Docs + Runbook + roadmap + CHANGELOG + state. |

### v0.3 deviations from the v0.2 design

- **Per-run `step_hook=` kwarg on `Agent.run` obviated, not
  shipped.** The v0.2 streaming server's transient
  `agent._on_step.append/remove` hack is gone now that
  `_stream_call` drives `agent.stream()` directly. The
  cleanup the kwarg would have unlocked has no remaining
  caller, so we don't add API surface speculatively.
- **`step` kind preserved in `StreamingChunkKind`.** It's no
  longer emitted by the default streaming server (which now
  forwards typed events from the strategy), but stays in the
  union so strategies that want step-level granularity can
  yield `StreamingEvent(kind="step", ...)` explicitly.
- **v0.2 `step` / `tool_call` / `tool_result` shape requires
  an opt-in `stream()` override.** Strategies that don't
  override `ReasoningStrategy.stream` now emit a single
  canonical `done` over A2A — same graduation behaviour as
  `ChatSession`. This is a breaking change for A2A clients
  that relied on the v0.2 per-step shape from a default
  strategy; documented here so callers either override
  `stream()` on their strategy or migrate to consuming the
  canonical `done` alone.
- **`A2AChunkKind` is now `agentforge_core`-owned.** The
  alias still lives at `agentforge_a2a.values` for backward
  compat, but the canonical definition is
  `agentforge_core.values.chat.StreamingChunkKind`.

### Out-of-scope (deferred to v0.4+)

- Central A2A registry service.
- Hardening the `live` CI job to gate merge.
- TS port.
- Overriding `ReasoningStrategy.stream` on built-in
  strategies (`ReActLoop`, etc.) — case-by-case.

## 11. Runbook

### How do I consume another agent?

```python
from agentforge_a2a import A2APeer, agent_call
from agentforge_a2a._inmem_runner import FakeA2AClientRunner

# Production: import httpx and write a thin runner that uses
# httpx.AsyncClient.post(...). For now (v0.4 chunk 2 stubs)
# inject a fake.
runner = FakeA2AClientRunner.with_response({"output": "ok", "run_id": "r"})
peer = A2APeer.from_config(
    {
        "name": "fact-checker",
        "url": "https://internal.fact-checker.example/a2a",
        "auth": {"type": "bearer", "token": "tok"},
    },
    runner=runner,
)
result = await agent_call(
    "fact-checker:verify",
    {"claim": "x"},
    peers={"fact-checker": peer},
    timeout_s=30,
    budget_usd=0.25,
)
print(result.output)
```

### How do I expose this agent?

```python
from agentforge import Agent, EnvBearerAuth
from agentforge_a2a import A2AServer

server = A2AServer(
    agent=Agent(model="anthropic:claude-sonnet-4-6", strategy="react"),
    auth=EnvBearerAuth("A2A_TOKENS"),
    endpoints=["review-pr", "verify"],
    host="0.0.0.0",
    port=8080,
)
await server.serve()
```

### How do I add mTLS?

Pass `{"type": "mtls", "cert": "/path/cert.pem", "key":
"/path/key.pem", "ca": "/path/ca.pem"}` as the `auth` field in
the peer config. `build_outgoing_auth(...)` builds a
`ClientAuth` with an `ssl.SSLContext`; httpx receives it
through the runner's `ssl_context=` argument.

### How do I debug auth failures?

`A2AAuthError` is the typed exception raised on
401/403/`{error: "unauthorized"}` responses. Catch it
explicitly to differentiate from generic transport
`A2ACallError`. The runner's request log includes the
`Authorization` header (redact before sharing).

### How do I wire from config?

```yaml
modules:
  protocols:
    - name: a2a
      config:
        peers:
          - name: fact-checker
            url: "https://internal.fact-checker.example/a2a"
            auth: {type: "bearer", token: "${FACT_CHECKER_TOKEN}"}
        expose:
          enabled: true
          host: "0.0.0.0"
          port: 8080
          endpoints:
            - name: "review-pr"
              description: "Review a pull request"
```

```python
from agentforge_a2a import A2ABridge
from agentforge import EnvBearerAuth
from agentforge_a2a._inmem_runner import FakeA2AClientRunner

bridge = A2ABridge.from_config(
    config.modules.protocols[0].config,
    agent=my_agent,
    auth=EnvBearerAuth("A2A_TOKENS"),
    client_runner=FakeA2AClientRunner(),  # swap for the production runner once live
)
await bridge.start()
```

`agentforge config validate` enforces the schema
automatically — `A2ABridge.config_schema` points at
`A2AConfig`, so feat-012's module-schema walker picks it up.

### How do I discover what a peer exposes? (v0.2)

```python
from agentforge_a2a import A2APeer, BearerAuth, discover_peer
from agentforge_a2a._runner import _HTTPXClientRunner

runner = _HTTPXClientRunner()
peer = A2APeer(
    name="fact-checker",
    url="https://internal.fact-checker.example/a2a/v1/calls",
    auth=BearerAuth(os.environ["FACT_CHECKER_TOKEN"]),
    runner=runner,
)
info = await discover_peer(peer, timeout_s=10.0)
for ep in info.endpoints:
    print(ep.name, "—", ep.description, ep.input_schema)
```

When you have multiple peers wired through `A2ABridge`,
`await bridge.discover_all()` probes them all and caches the
results on `bridge.peer_info`.

### How do I stream a long-running agent call? (v0.3)

```python
from agentforge_a2a import agent_call_stream

async for chunk in agent_call_stream(
    "fact-checker:verify",
    {"claim": "x"},
    peers={"fact-checker": peer},
    timeout_s=60.0,
    budget_usd=0.25,
):
    if chunk.kind == "text":
        print(chunk.content, end="", flush=True)
    elif chunk.kind in {"thinking", "step", "tool_call", "tool_result"}:
        print(f"\n[{chunk.kind}] {chunk.content}")
    elif chunk.kind == "done":
        print("\ndone →", chunk.content)
    elif chunk.kind == "error":
        # agent_call_stream raises A2AAuthError / A2ACallError
        # on error frames — this branch is for completeness.
        raise RuntimeError(chunk.content)
```

v0.3 ships true per-token streaming via
`ReasoningStrategy.stream()`. Each event the strategy yields
becomes one SSE frame on the wire; the server emits its own
canonical `done` with `output` + `cost_usd` + `run_id` after
the strategy completes.

Strategies that **don't** override `ReasoningStrategy.stream`
fall through to the default ABC implementation and emit a
single `done` event — same graduation behaviour as
`ChatSession`. Override `stream()` on your strategy to get
per-token granularity.

### How do I expose per-token streaming on my strategy? (v0.3)

```python
from collections.abc import AsyncIterator

from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.values.chat import StreamingEvent
from agentforge_core.values.state import AgentState, Step


class MyTokenStrategy(ReasoningStrategy):
    async def run(self, state: AgentState) -> AgentState:
        # Unary callers still call run(); append a final step
        # so Agent._extract_output picks up the answer.
        state.steps.append(Step(iteration=0, kind="synthesize", content="final"))
        return state

    async def stream(self, state: AgentState) -> AsyncIterator[StreamingEvent]:
        async for token in self._llm_stream(state.task):
            yield StreamingEvent(kind="text", content=token)
        state.steps.append(Step(iteration=0, kind="synthesize", content="final"))
        # Always yield a terminal `done`; Agent.stream swallows it
        # and emits its own canonical done with the full RunResult.
        yield StreamingEvent(kind="done", content={"run_id": state.run_id})
```

### How do I run the live A2A tests?

```bash
uv run pytest -m live packages/agentforge-a2a/tests/integration/
```

Each test spins up a real `uvicorn.Server` on a random
localhost port, points a real `_HTTPXClientRunner` at it,
round-trips the three flows (`agent_call` / `discover_peer` /
`agent_call_stream`), and tears down. The default
pre-commit + CI gate skips this suite via `-m "not live"`; CI
runs it in a dedicated non-gating `live` job.

## 12. References

- A2A spec: https://github.com/google/A2A
- feat-001, feat-007 (run_id, budget)
- Prior art: A2A protocol support in other agent frameworks
