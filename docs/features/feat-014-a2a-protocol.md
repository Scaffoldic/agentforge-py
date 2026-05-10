# feat-014: A2A protocol support

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-014 |
| **Title** | Agent-to-Agent (A2A) protocol — cross-framework agent calls |
| **Status** | proposed |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.4 (after stability bar reached on core) |
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

## 10. References

- A2A spec: https://github.com/google/A2A
- feat-001, feat-007 (run_id, budget)
- Prior art: Strands Agents A2A support
