# ADR-0019: `ChatSession` as wrapper over `Agent` (not a new class)

## Metadata

| Field | Value |
|---|---|
| **Number** | 0019 |
| **Title** | `ChatSession` as wrapper over `Agent` (not a new class) |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | architecture, deployment |

---

## 1. Context and problem statement

`Agent.run(task) -> RunResult` is one-shot: the framework's primary
abstraction. Conversational deployments (chatbots, copilots) need
multi-turn state, streaming, session management, HTTP/WebSocket
exposure. The chat shape is real — but how does it relate to `Agent`?

Three architectural choices:
- Add a chat surface directly to `Agent` (e.g. `agent.chat(session_id,
  msg)`)
- Make `ChatAgent` a separate class with its own contracts
- Build `ChatSession` as a wrapper over an existing `Agent`

How do we add chat support without compromising the simplicity of the
core `Agent`?

## 2. Decision drivers

- Most agents are one-shot; chat shouldn't bloat the core
- Chat must reuse every primitive (tools, multi-provider, memory,
  guardrails, evaluators, observability, budget) for free
- Two parallel APIs in one library is a known anti-pattern
- Future deployment shapes (voice, IDE plugin, etc.) shouldn't each
  spawn a new class

## 3. Considered options

1. **Chat methods on `Agent`** — `agent.chat(session_id, message)` and
   `agent.run(task)` both available
2. **Separate `ChatAgent` class** — own constructor surface
3. **`ChatSession` wraps `Agent`** — `ChatSession(agent)` adds turn
   history, streaming, session lifecycle on top
4. **External chat-server framework** — chat is not a framework concern

## 4. Decision outcome

**Chosen: Option 3 — `ChatSession` wraps `Agent`.**

`Agent` stays one-shot. `ChatSession` is a new class (in
`agentforge-chat`) that takes an `Agent` instance, owns conversation
history (via `ChatHistoryStore`), and provides `send` and `stream`
methods. Per-turn lifecycle: each `session.send(msg)` becomes one
`agent.run(task)` with augmented context (system prompt + truncated
history + user message). Each turn gets its own `run_id`; session_id
is metadata.

This wrapper pattern — repeated for `ChatServer` (HTTP/WebSocket
server in `agentforge-chat-http`) and `A2AServer` (cross-framework
calls in `agentforge-a2a`) — establishes a uniform "deployment shape"
pattern: every shape wraps `Agent` without changing it.

### Positive consequences

- `Agent` stays small and focused on one-shot execution
- Chat reuses every framework primitive without one line of new code
- Future deployment shapes follow the same pattern
- Chat is opt-in via `pip install agentforge-chat` — non-chat agents
  never see it

### Negative consequences (trade-offs)

- Two classes to learn (Agent + ChatSession) — but only when chat is
  in scope
- Per-turn `agent.run` cost slightly higher than a hypothetical
  in-loop chat; benchmarked acceptable
- Custom strategies must support being called per-turn (true by
  design; verified in conformance)

## 5. Pros and cons of the options

### Option 1: Chat methods on Agent

- + One class
- − Bloats Agent; mixes one-shot + multi-turn semantics
- − Forces all agents to depend on chat machinery

### Option 2: Separate ChatAgent class

- + Clean per-shape API
- − Duplicates Agent's surface; risk of two parallel APIs
- − Tools/memory/etc. must be re-exposed

### Option 3: Wrapper (chosen)

- + Reuses everything; no duplication
- + Pattern extends to A2A, voice, IDE etc.
- − Two-class mental model

### Option 4: External chat-server framework

- + Smaller core
- − Defeats the goal of providing production-ready conversational agents

## 6. References

- [`docs/features/feat-001-core-contracts-and-agent.md`](../features/feat-001-core-contracts-and-agent.md)
- [`docs/features/feat-020-chat-agents.md`](../features/feat-020-chat-agents.md)
- [`docs/design/architecture.md`](../design/architecture.md) §7b
