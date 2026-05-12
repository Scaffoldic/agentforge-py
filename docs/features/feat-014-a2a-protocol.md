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
because one team uses LangGraph, another uses CrewAI, your team uses
AgentForge — you need a protocol.

A2A (Agent-to-Agent) is the emerging standard for cross-framework agent
invocation. Strands ships it. Google's ADK ships it. We need to support it
to participate in the multi-agent ecosystem.

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
  frameworks (LangGraph, CrewAI, Claude Desktop) can call it.
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

- Production runner against a real A2A peer (live
  integration test).
- A2A discovery / registry (spec §9).
- Bi-directional streaming (spec §9).
- TS port.

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

## 12. References

- A2A spec: https://github.com/google/A2A
- feat-001, feat-007 (run_id, budget)
- Prior art: Strands Agents A2A support
