# ADR-0014: Async-first core in both languages

## Metadata

| Field | Value |
|---|---|
| **Number** | 0014 |
| **Title** | Async-first core in both languages |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | architecture, concurrency |

---

## 1. Context and problem statement

Agent runtimes are I/O-heavy: LLM calls, tool calls, memory writes,
HTTP calls all block on network. A synchronous core would limit
concurrency to threads (with their cost and complexity) or force users
to wrap everything themselves.

How do we expose the framework's API so it stays performant in
production deployments (chat servers, multi-tenant runtimes, A2A
peers) without making notebook / script use awkward?

## 2. Decision drivers

- Agents make many concurrent I/O calls; async is the right primitive
- Modern Python (3.11+) has mature asyncio; modern Node has native promises
- TS frontend integration (chat servers, websockets) is async-native
- Notebook users prefer sync surface
- Mixing sync and async in one library is a known footgun

## 3. Considered options

1. **Sync-only core** — wraps async internally
2. **Async-only core** — every public method is `async def`
3. **Dual surface** — every method has sync and async variants
4. **Async-first + thin sync shim** — core is async; a `Agent.run_sync()`
   convenience wrapper exists for notebooks/scripts

## 4. Decision outcome

**Chosen: Option 4 — Async-first + thin sync shim.**

All public methods on locked contracts are `async def` (Python) /
`async ... Promise<T>` (TypeScript). For notebook/script use, every
top-level entry point gets a `*_sync` shim that wraps `asyncio.run()`.
Tools may be sync or async — sync tools are wrapped in
`asyncio.to_thread` automatically. Strategies, providers, memory,
evaluators, validators are all async at the contract level.

This matches Pydantic AI, smolagents-toolkit, AutoGen v0.4, and modern
FastAPI / Hono — async-first is the 2026 default for I/O frameworks.

### Positive consequences

- Optimal concurrency in production
- Streaming, cancellation, parallel tool calls are natural
- Match for HTTP/WebSocket server (chat-http, A2A) without translation
- Notebook users get `run_sync()` ergonomics

### Negative consequences (trade-offs)

- Async is harder to teach than sync
- Sync tools require `asyncio.to_thread`; documented but adds an
  edge-case category
- Stack traces in async code can be longer

## 5. Pros and cons of the options

### Option 1: Sync-only

- + Simple
- − Production performance hostile; concurrency forced to threads

### Option 2: Async-only

- + Clean
- − Notebook / quick-script use awkward

### Option 3: Dual surface

- + Best of both
- − Doubles the public surface; bug surface doubles too

### Option 4: Async-first + sync shim (chosen)

- + Production-optimal
- + Notebook-friendly via shim
- − Async teaching tax remains for new users

## 6. References

- [`docs/design/architecture.md`](../design/architecture.md) §10
- ADR-0007 (ABC + Protocol contracts — defined async)
- Prior art: Pydantic AI, AutoGen v0.4, FastAPI, Hono
