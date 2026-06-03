# feat-020: Chat agents — `ChatSession`, `ChatHistoryStore`, `ChatServer`

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-020 |
| **Title** | Chat agents — stateful conversation wrapper over `Agent` + history store + HTTP/WebSocket server |
| **Status** | shipped (Python v0.2 scope) |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.1 (contracts + memory + sqlite drivers + chat-http server — shipped); 0.2 (postgres + redis drivers + Slack reference adapter + real per-token streaming + cross-process locking + provider-aware tokeniser) |
| **Languages** | both |
| **Module package(s)** | `agentforge-chat` (core + in-memory + sqlite drivers), `agentforge-chat-history-postgres`, `agentforge-chat-history-redis`, `agentforge-chat-http`, optional channel adapters |
| **Depends on** | feat-001, feat-003 (streaming capability), feat-005, feat-007 (run_id, budget, idempotency), feat-009 (session-level traces), feat-014 (auth backends reused), feat-018 (per-turn guardrails) |
| **Blocks** | none |

---

## 1. Why this feature

AgentForge today is one-shot: `agent.run(task)` produces a `RunResult`,
and the next call has no memory of the last. That is correct for CLI
agents, batch processing, code reviewers, and most production agentic
systems — but it leaves a major use case unsupported: **conversational
agents** (chatbots, copilots, assistants) where each user turn must
respond in the context of the prior conversation.

Pain we are removing:

- **Boilerplate for "remember the conversation."** Every team builds
  their own message buffer, their own truncation rule, their own
  storage layer. None of it composes; none of it integrates with the
  framework's tools / memory / guardrails.
- **No streaming surface.** Modern chat UX expects token-by-token
  output. Without it, users stare at a spinner for 10 seconds.
- **No HTTP/WebSocket exposure.** Wiring a FastAPI server around an
  `Agent` is straightforward but reinvented per project, with
  inconsistent semantics for cancellation, sessions, idempotency.
- **No multi-tenant isolation.** Two users sharing one server must not
  see each other's history. Per-team implementations get this wrong.
- **No production-grade history backend choice.** Real chatbots run
  millions of sessions; SQLite isn't enough. Teams reach for Redis or
  Postgres themselves and drift from the framework.

## 2. Why it must ship as framework

- **Wrapping `Agent` correctly is non-trivial.** Per-turn `run_id`,
  per-turn budget, per-turn guardrail invocation, per-turn audit, plus
  cancellation that cleanly aborts in-flight LLM calls, plus
  concurrency control per session — getting these right takes weeks
  per team. One framework-owned implementation amortises the work.
- **`ChatHistoryStore` is the new persistent boundary** for chat-shaped
  agents, distinct from `MemoryStore` (claims). It needs the same
  multi-driver, swap-without-rewrite story (sqlite → postgres → redis).
- **Streaming protocol must be uniform.** Chunk shape (`text`,
  `tool_call`, `tool_result`, `done`, `error`) is the wire contract
  between agent and UI; framework owns it.
- **Multi-tenant safety is a framework concern.** Default-on
  isolation, never bleed between session_ids. Per-agent invention
  would get this wrong eventually.
- **Without framework ownership:** every chat agent ships its own
  half-broken session manager; cross-agent observability impossible;
  upgrade story dies because chat plumbing is per-team.

## 3. How derived agents benefit

- **Three lines from one-shot to chat.**
  ```python
  from agentforge import Agent
  from agentforge.chat import ChatSession
  agent = Agent(model="reasoning", tools=[...])
  session = ChatSession(agent)
  print(await session.send("Hi"))
  print(await session.send("What did I just say?"))   # remembers
  ```
- **All existing primitives apply.** Tools, multi-provider, evaluators,
  guardrails, memory (claims), observability — every one of them works
  inside chat without one line of new code.
- **Streaming with one method.** `async for chunk in session.stream(msg):`
  yields typed chunks suitable for any UI.
- **Production HTTP server with `pip install`.** `agentforge-chat-http`
  ships REST + WebSocket + SSE; auth via the same `AuthPolicy` ABCs as
  feat-014.
- **Backend swap.** SQLite for MVP; switch to Postgres or Redis with
  one config edit. Same `ChatHistoryStore` ABC.
- **Per-turn run_id.** Every turn shows up as a normal AgentForge run
  with traces, budget, evaluator scores; the session_id is metadata.
  Every existing dashboard works.
- **Truncation strategies built in.** Sliding window, token budget,
  summarisation — pick by config, change anytime.
- **Multi-tenant isolation by default.** `session_id` is the
  isolation key; explicit cross-session access is a verb, not an
  accident.

## 4. Feature specifications

### 4.1 User-facing experience

**Library use:**

```python
from agentforge import Agent
from agentforge.chat import ChatSession
from agentforge.chat.history import SqliteChatHistory
from agentforge.chat.truncation import TokenBudget

agent = Agent(model="reasoning", tools=[...])

session = ChatSession(
    agent=agent,
    session_id="user-42-thread-1",
    history_store=SqliteChatHistory(path="./chat.db"),
    system_prompt="You are a careful research assistant.",
    truncation=TokenBudget(max_tokens=64_000),
    per_turn_budget_usd=0.50,
    per_session_budget_usd=10.00,
    owner="user-42",
)

# Single-shot per turn
response = await session.send("Tell me about Voyage embeddings.")
print(response.content)
print(response.cost_usd, response.run_id)

# Streaming per turn
async for chunk in session.stream("And how do they compare to OpenAI's?"):
    if chunk.kind == "text":
        print(chunk.content, end="", flush=True)
    elif chunk.kind == "tool_call":
        print(f"\n[calling {chunk.content['name']}]")

# Inspect / manage
turns = await session.history(limit=10)
await session.reset()                      # clears history; session_id stays
await session.close()                      # flushes + releases
```

**HTTP server:**

```python
from agentforge.chat.http import ChatServer
from agentforge.chat.http.auth import BearerAuth

server = ChatServer(
    agent_factory=lambda: build_agent(),     # called per session
    history_store=PostgresChatHistory.from_env(),
    auth=BearerAuth.from_env("API_TOKENS"),
    host="0.0.0.0", port=8080,
    cors_origins=["https://chat.example.com"],
)
await server.serve()
```

**HTTP API:**

```
POST   /sessions                            -> create new session, returns id
GET    /sessions                            -> list sessions for the auth principal
DELETE /sessions/{id}                       -> delete session + history
POST   /sessions/{id}/messages              -> send a message, return response
                                               Accept: text/event-stream → SSE
                                               Accept: application/json → buffered
GET    /sessions/{id}/messages?before=...   -> paginated history
WS     /sessions/{id}/ws                    -> bidirectional streaming
GET    /healthz                             -> liveness
```

### 4.2 Public API / contract

**Locked contracts (in `agentforge-core` for cross-language compatibility):**

```python
# agentforge_core/contracts/chat.py
class ChatTurn(BaseModel):
    id: str                        # ULID, monotonic
    session_id: str
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    timestamp: datetime
    run_id: str | None             # links to the AgentForge run that produced this
    tool_calls: list[ToolCall] | None = None
    tool_call_id: str | None = None    # for role="tool"
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0
    metadata: dict[str, Any] = {}

class SessionInfo(BaseModel):
    id: str
    owner: str | None
    created_at: datetime
    last_active_at: datetime
    turn_count: int
    total_cost_usd: float
    metadata: dict[str, Any] = {}

class ChatHistoryStore(ABC):
    """Persistent store for chat turns. Multi-tenant by session_id.

    All methods scoped by session_id; cross-session access is impossible
    without explicitly passing the id.
    """
    @abstractmethod
    async def append(self, turn: ChatTurn) -> None: ...
    @abstractmethod
    async def load(
        self,
        session_id: str,
        *,
        limit: int | None = None,
        before: datetime | None = None,
        after: datetime | None = None,
        roles: list[str] | None = None,
    ) -> list[ChatTurn]: ...
    @abstractmethod
    async def count(self, session_id: str) -> int: ...
    @abstractmethod
    async def delete_session(self, session_id: str) -> int: ...    # returns turns deleted
    @abstractmethod
    async def list_sessions(
        self,
        *,
        owner: str | None = None,
        limit: int = 100,
        before: datetime | None = None,
    ) -> list[SessionInfo]: ...
    @abstractmethod
    async def update_session_metadata(self, session_id: str, metadata: dict) -> None: ...
    # Concrete default (bug-018): register a session before its first turn.
    async def create_session(
        self, session_id: str, *, owner: str | None = None, metadata: dict | None = None
    ) -> None: ...
    @abstractmethod
    async def expire_before(self, cutoff: datetime) -> int: ...    # TTL sweep
    @abstractmethod
    async def close(self) -> None: ...

    def capabilities(self) -> set[str]:
        """Subset of: 'ttl', 'encryption_at_rest', 'full_text_search',
        'streaming_load'."""
        return set()

class HistoryTruncationStrategy(ABC):
    """Decides which turns from history to include in the next LLM call."""
    @abstractmethod
    async def select(
        self,
        all_turns: list[ChatTurn],
        next_user_message: str,
        context: dict[str, Any],
    ) -> list[ChatTurn]: ...

# Built-ins in agentforge-chat:
#   SlidingWindow(max_turns=50)
#   TokenBudget(max_tokens=...)
#   SummariseOldest(threshold_turns=30, summariser_provider="fast-judge")
#   Hybrid(SlidingWindow, TokenBudget)            # composable
```

**Non-locked (in `agentforge-chat`) — may evolve:**

```python
class ChatSession:
    def __init__(
        self,
        agent: Agent,
        *,
        session_id: str | None = None,           # auto-generates ULID
        history_store: ChatHistoryStore | None = None,    # default InMemory
        system_prompt: str | Callable[[ChatContext], str] | None = None,
        truncation: HistoryTruncationStrategy | None = None,    # default SlidingWindow(50)
        owner: str | None = None,
        per_turn_budget_usd: float | None = None,
        per_session_budget_usd: float | None = None,
        idempotency_window_s: int = 60,
        on_turn: Callable[[ChatTurn], None] | None = None,
    ) -> None: ...

    async def send(
        self, message: str, *, idempotency_key: str | None = None,
    ) -> ChatResponse: ...

    async def stream(
        self, message: str, *, idempotency_key: str | None = None,
    ) -> AsyncIterator[ChatChunk]: ...

    async def history(self, **kwargs) -> list[ChatTurn]: ...
    async def reset(self) -> None: ...
    async def close(self) -> None: ...

    @property
    def total_cost_usd(self) -> float: ...
    @property
    def turn_count(self) -> int: ...
    @property
    def session_id(self) -> str: ...

class ChatResponse(BaseModel):
    content: str
    turn_id: str
    run_id: str
    tool_calls: list[ToolCall]
    tokens_in: int
    tokens_out: int
    cost_usd: float
    duration_ms: int
    finished_reason: str

class ChatChunk(BaseModel):
    kind: Literal["text", "tool_call", "tool_result", "thinking", "done", "error"]
    content: str | dict[str, Any] | None
    cumulative_text: str | None      # incremental concatenation so far
    turn_id: str
    metadata: dict[str, Any] = {}
```

### 4.3 Internal mechanics

**Per-turn lifecycle** (`session.send(msg)`):

```
  1. Acquire per-session lock (only one in-flight turn per session_id).
  2. If idempotency_key matches a recent turn within window: return cached response.
  3. Build an incoming ChatTurn(role="user", content=msg, session_id=...).
  4. Run feat-018 InputValidators on `msg` (BLOCK on violation).
  5. Append the user turn to history_store.
  6. Load+truncate prior turns via HistoryTruncationStrategy.
  7. Build agent task: system_prompt + selected_history + user_msg.
  8. agent.run(task)            — own run_id, own budget, own everything.
  9. Run feat-018 OutputValidators on the response (REDACT or BLOCK on violation).
 10. Append assistant ChatTurn(role="assistant", content=..., run_id=run_id, ...).
 11. (If tool calls happened during the run, those are stored as separate
     ChatTurn(role="tool", tool_call_id=...) items, attributed to the same run_id.)
 12. Update session metadata (last_active_at, total_cost_usd).
 13. Release per-session lock.
 14. Return ChatResponse.
```

**Streaming** (`session.stream(msg)`):

```
  Same lifecycle 1-7.
  agent.stream(task) is the streaming path (requires LLM provider's
  streaming capability per feat-003).
  As chunks arrive:
    - Stream text chunks immediately.
    - Stream tool_call chunks when a tool is invoked.
    - Run tool, stream tool_result.
    - Continue.
  On completion:
    - Run output validators on FULL accumulated text (not per-chunk; some
      validators need full content).
    - If validators redact, stream a 'replacement' chunk; document that
      streaming + redaction may surface the redact AFTER the original text.
      Recommend strict mode: buffer entire response, run validators, then
      stream — controlled by `safety_mode: "buffer-then-stream" | "stream-then-redact"`.
    - Stream `done` chunk with cumulative cost / tokens / turn_id.
  On client disconnect:
    - Cancellation token fires → agent.run aborts → partial cost is recorded
      → assistant turn marked 'cancelled' in metadata.
```

**Concurrency model:**

- **Per-session:** one in-flight turn at a time. Concurrent `send()` on
  same session_id queues (configurable: queue / reject / replace).
- **Cross-session:** fully concurrent. Lock granularity is `session_id`.
- **Implementation:** in-process `asyncio.Lock` per session_id, weak-ref
  cleaned up on session close. For multi-process (HTTP server with
  multiple workers), use the history store's optimistic-write pattern
  (rejected appends retried) or a Redis-backed lock if needed.

**Cancellation:**

- `send`/`stream` accept a `cancellation_token` parameter (Python
  `asyncio.Event` or TS `AbortSignal`).
- WebSocket disconnects auto-fire cancellation.
- `agent.run()` honours cancellation between iterations and during LLM
  streaming (drops the stream).
- Partial cost is committed; partial assistant turn is appended with
  `metadata.cancelled = True`.

**Idempotency:**

- If `idempotency_key` provided, recent turns (within `idempotency_window_s`)
  are searched for a matching key on the user role.
- If found, the prior assistant turn is returned without re-running the
  agent. No double-charge.
- Key is supplied by the *caller* (typically the HTTP layer on a retried
  POST). For unkeyed sends, no idempotency.

**Multi-tenant isolation:**

- `session_id` is the isolation key. `ChatHistoryStore` operations are
  always parameterised by `session_id`.
- `owner` field on `SessionInfo` is the tenant identity. `list_sessions`
  filters by `owner` automatically when authenticated; bypass requires
  explicit `owner=None` in code (audit-loggable).
- HTTP server enforces ownership: a request authenticated as user-42
  cannot read user-99's sessions.

**Audit:**

- Every turn append, every guardrail decision, every session create/
  delete emits a structured event on the `agentforge.audit` channel
  (feat-018) with `run_id` and `session_id`.

### 4.4 Module packaging

| Package | Provides | Available from |
|---|---|---|
| `agentforge-chat` | `ChatSession`, ABCs (`ChatHistoryStore`, `HistoryTruncationStrategy`), `InMemoryChatHistory`, `SqliteChatHistory`, all 4 truncation strategies | 0.2 |
| `agentforge-chat-history-postgres` | `PostgresChatHistory` driver | 0.3 |
| `agentforge-chat-history-redis` | `RedisChatHistory` driver — fast in-memory with native TTL | 0.3 |
| `agentforge-chat-http` | `ChatServer` — FastAPI (Py) / Hono (TS) — REST + WebSocket + SSE; reuses `AuthPolicy` from feat-014 | 0.2 |
| `agentforge-chat-slack` (reference adapter) | Slack channel adapter as exemplar of community pattern | 0.3 |

**The contracts above are designed to support all four backends from
day 1**, even though Postgres and Redis drivers ship at 0.3. A team
that wants Postgres before 0.3 implements the ABC themselves — the
contract is stable from 0.2.

### 4.5 Configuration

```yaml
# agentforge.yaml — chat-enabled agent

providers:
  reasoning:
    type: anthropic
    model: "claude-sonnet-4.7"
  summariser:                              # used by SummariseOldest truncation
    type: anthropic
    model: "claude-haiku-4-5"

agent:
  model: "reasoning"
  llm_options:
    streaming: true                        # required for chat streaming

modules:
  chat:
    history:
      driver: postgres                     # memory | sqlite | postgres | redis
      config:
        dsn: "${POSTGRES_DSN}"
        pool: { min_size: 2, max_size: 20 }
        ttl_days: 90                       # auto-expiration sweep
    truncation:
      strategy: hybrid
      max_turns: 100
      max_tokens: 64000
      summariser_provider: "summariser"
      summarise_threshold_turns: 50
    session:
      per_turn_budget_usd: 0.50
      per_session_budget_usd: 10.00
      concurrency: queue                   # queue | reject | replace
      idempotency_window_s: 60
      safety_mode: "buffer-then-stream"    # safer; or "stream-then-redact" for lower latency

  chat_http:                               # for agentforge-chat-http
    host: "0.0.0.0"
    port: 8080
    cors_origins: ["https://chat.example.com"]
    auth:
      type: bearer
      tokens_env: "API_TOKENS"
    rate_limit:
      per_session_per_minute: 30
      per_owner_per_minute: 120
```

## 5. Plug-and-play & upgrade story

`agentforge add module chat` installs the core; subsequent
`add module chat-http`, `chat-history-postgres`, `chat-history-redis`
are pip-install-and-config-edit. ABCs locked from 0.2 — driver swaps
require no code change in the agent.

Upgrade-safe: `ChatSession` constructor surface follows the same
semver discipline as `Agent` (P8). Streaming chunk kinds are a closed
enum at the contract level; new kinds require a minor bump with a
default ignore on the receiver side.

## 6. Cross-language parity

ABC + value type contracts identical in Python and TS. Driver
landings:

- v0.2: Python ships memory + sqlite + chat-http (FastAPI). TS ships
  memory + chat-http (Hono); SQLite at v0.3.
- v0.3: Postgres + Redis in both languages.
- Hono and FastAPI are independently chosen for their ecosystems;
  the API surface (`ChatServer.serve()`) is identical. The HTTP wire
  format is the same.

## 7. Test strategy

- **Conformance suite** for `ChatHistoryStore`: every driver passes 30+
  tests (CRUD, isolation by session_id, owner filtering, TTL sweep,
  pagination, capability honesty).
- **Conformance for `HistoryTruncationStrategy`:** monotone behaviour
  (more turns in → never fewer turns out); preserves invariants
  (first user turn always kept; tool-call/tool-result pairs not split).
- **Isolation test:** two `ChatSession`s in same process with different
  session_ids cannot read each other's history under any code path.
- **Concurrency test:** 100 concurrent sends to the same session
  produce a strictly serialised history; no interleaving.
- **Cancellation test:** WebSocket disconnect aborts the in-flight
  agent run within 200ms; partial cost recorded.
- **Idempotency test:** same `idempotency_key` within window returns
  cached response; outside window creates new turn.
- **Streaming + safety test:** `safety_mode: buffer-then-stream`
  produces no leaked PII even when LLM emits it; `stream-then-redact`
  surfaces the leak then patches.
- **HTTP integration:** ChatServer end-to-end with a real Agent and
  real (in-memory) history; WebSocket round-trip; SSE round-trip;
  REST round-trip.
- **Multi-process safety:** when chat-http runs with multiple workers,
  per-session lock honoured via the history-store-level optimistic
  pattern; conformance test simulates with 4 workers.
- **Cost-aggregation test:** per-turn + per-session budgets enforced;
  budget exhaustion returns a clean 402-equivalent response.

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| History grows unboundedly | Truncation strategies built-in; TTL sweep on stores that support it; `expire_before` API on every driver |
| Tool-call/tool-result pair split by truncation | Truncation strategies enforce pair atomicity (drop both or keep both); covered by conformance test |
| Streaming + output validation fundamentally conflict (you can't validate text you haven't seen) | Two modes: `buffer-then-stream` (safe, higher latency) and `stream-then-redact` (low latency, may briefly leak); documented; default safer |
| WebSocket cancellation reliability across proxies/load balancers | Document; recommend SSE for HTTP/1.1-only paths; provide a `keepalive_seconds` config |
| Multi-process locking when scaling beyond one chat-http worker | History store supports optimistic-append; for strict serialisation, opt-in Redis lock |
| Session-id collision / spoofing | Session_id auto-generated as ULID; HTTP server validates session ownership against authenticated principal on every request |
| Massive sessions (10k+ turns) bog down `load()` | Pagination required; conformance test asserts query plan stays sub-linear w.r.t. session size |
| LLM context window overflows when history is too long | TruncationStrategy is responsible; `TokenBudget` strategy uses provider's tokeniser; runs *before* the LLM call |
| Privacy / right-to-delete | `delete_session()` cascades; audit-logged; documented as the GDPR/CCPA surface |
| Encryption at rest | Capability flag `"encryption_at_rest"`; Postgres driver supports via pgcrypto; Redis via redisson encryption; SQLite via SQLCipher (optional extra) |
| Cross-channel session continuity (user starts on web, continues on Slack) | Out of v0.x scope; design accepts it via shared `owner` + custom session_id mapping; explicit non-goal |
| Conversation branching/forking ("regenerate response") | Out of v0.x scope; ChatTurn schema includes optional `parent_turn_id` so future branching is non-breaking |
| Voice / audio | Out of scope; speech-to-text and text-to-speech belong in tools or a separate feature |
| Should ChatSession run guardrail input validation BEFORE storing the user turn? | Yes — never persist content that violated input policy; conformance test covers |
| Backpressure on streaming when client can't keep up | WebSocket: framework drops if buffer exceeds `max_buffered_chunks`; documented; SSE relies on HTTP/2 flow control |
| Tool calls embedded in stream UX | `ChatChunk(kind="tool_call")` and `kind="tool_result"` chunks emitted in-band; UI renders them between text segments; spec'd in chat-http API doc |
| Multiple ChatSessions sharing one Agent (memory contention)? | Documented: agents are stateless in run(); sharing is fine; per-turn run_id keeps traces separate; recommend one Agent per ChatSession in production for clarity |

## 9. Out of scope

- **Voice / audio I/O.** Speech-to-text and text-to-speech are tools,
  not chat-loop primitives. A future feature may add audio chunk
  kinds; not now.
- **Cross-channel session continuity** (web → Slack → email). Out of
  v0.x; the schema accepts it but the framework doesn't bridge.
- **Conversation branching** ("regenerate this response," "explore
  alternative path"). Schema admits parent_turn_id for forward
  compatibility; UI affordances out of scope until v0.x consumers ask.
- **Real-time multi-user chat in one session** (collaborative
  conversations). Out of scope — sessions are 1-user-1-conversation.
- **Built-in moderation classifier.** Use feat-018 guardrails
  (Llama Guard, Perspective API integration via custom validator).
  Chat doesn't reinvent.
- **A web chat widget / frontend.** The framework provides the API;
  frontends are application code (or community packages). Not framework
  scope.
- **LLM provider's "session" or "thread" primitives** (e.g. OpenAI
  Assistants threads). We do not bind to a vendor's hosted-state model;
  ChatHistoryStore is the source of truth so portability is preserved.
- **Long-running async tasks ("get back to me when you've finished")**.
  Chat assumes synchronous-ish turns. Async work belongs in a job
  system the agent calls into.

## 10. References

- [`architecture.md`](../design/architecture.md) §6, §7
- [`design-principles.md`](../design/design-principles.md) — P1, P2,
  P3, P4, P6, P8, P9, P11
- feat-001 (Agent — wrapped per turn)
- feat-003 (LLM streaming capability + multi-provider for summariser)
- feat-005 (`MemoryStore` is *separate* from `ChatHistoryStore`; both
  may be active in the same agent — claims and chat history are
  different things)
- feat-007 (run_id, budget, idempotency — reused per turn)
- feat-009 (session_id propagated as OTel attribute on every span)
- feat-014 (`AuthPolicy` reused by ChatServer)
- feat-018 (per-turn input/output validators + per-tool-call gates)
- Prior art: Letta (server-resident chat agents); Pydantic AI
  conversation (similar wrapper pattern); Vercel AI SDK chunk shape;
  OpenAI Assistants threads; Slack Bolt SDK

## 11. Implementation status (Python — v0.2 scope)

Shipped in PR #26. Three workspace members went up together:
`agentforge-core` extensions, the new `agentforge-chat`, and
the new `agentforge-chat-http`.

| Chunk | Commit | What landed |
|---|---|---|
| 1 | `2bd8f38` | `agentforge_core.contracts.chat.{ChatHistoryStore, HistoryTruncationStrategy}` ABCs + `agentforge_core.values.chat.{ChatTurn, SessionInfo, ChatChunk, ChatResponse}` frozen value models + `run_chat_history_conformance` / `run_truncation_conformance` harnesses. |
| 2 | `d6d0a73` | `agentforge-chat` workspace member: `InMemoryChatHistory` + `SqliteChatHistory` (mirrors `SqliteMemoryStore`) + four truncation strategies (sliding-window, token-budget, summarise-oldest, hybrid). Entry-points under `agentforge.chat.history` / `agentforge.chat.truncation`. Pair-atomicity helper enforces tool-call/tool-result invariants. |
| 3 | `e4ff78d` | `ChatSession` (send + stream + history + reset + close + idempotency + budgets) wired through the agent's input/output guardrails. Per-session lock registry (`WeakValueDictionary`); LRU+TTL idempotency cache; sentence-segmenting `stream()` using the spec's `buffer-then-stream` default. |
| 4 | `200b38e` | `agentforge-chat-http` workspace member: FastAPI `ChatServer` with REST + WS + SSE + bearer-auth + in-process rate limiting + cross-owner 403 enforcement. `BearerAuthPolicy` ABC + `EnvBearerAuth` placeholder (refactors to feat-014's `AuthPolicy` when shipped). |
| 5 | `1369c95` | `modules.chat:` config block (`ChatHistoryDriverConfig`, `ChatTruncationConfig`, `ChatSessionConfig`, `ChatConfig`) + module-schema validation hook + `build_chat_session_from_config(config, agent)` + `register_chat_history` / `register_chat_truncation` resolver helpers. |
| 6 | (this PR) | Docs + Runbook + roadmap + CHANGELOG + state. |

### Deviations from the design

- **Streaming is buffer-then-stream only.** The strategy ABC
  has no `stream()` method yet; v0.2 runs the agent to
  completion and emits the assistant turn as sentence-segmented
  `ChatChunk(kind="text")` chunks followed by a `done`
  chunk. The wire format is correct; real per-token streaming
  becomes a no-API-break enhancement when the strategy
  contract grows streaming.
- **Cancellation is pre-LLM only.** The cancellation event is
  honoured between `history.load()` and `agent.run()`;
  mid-LLM cancellation requires the same strategy-streaming
  work. WS disconnect propagates a `set()` to the in-flight
  consume coroutine.
- **Single-process locking only.** Per-session
  `asyncio.Lock` lives in a `WeakValueDictionary` keyed by
  `session_id`. Cross-process locking (Redis) is deferred to
  v0.3 alongside the Redis driver.
- **`BearerAuthPolicy` is a v0.2-local stub.** feat-014's real
  `AuthPolicy` contract hasn't shipped yet; the chat-http
  policy becomes a thin adapter when it does.
- **Approximate token counting in `TokenBudget`.** Uses a
  4-chars-per-token heuristic. Provider-aware tokenisation is
  a v0.3 follow-up.
- **Postgres / Redis history drivers + Slack reference
  adapter** — all deferred to separate v0.3 PRs once each
  driver has a live-service test path.
- **TypeScript port** deferred (contract is locked).

### Open items

(All v0.2 follow-up items shipped — see the "v0.2 follow-up"
subsection below for the per-chunk commit table.)

Remaining for v0.3+:

- A2A per-token streaming via the new `ReasoningStrategy.stream()`
  ABC method (separate feat-014 follow-up PR; the contract +
  consumer paths are in place after v0.2).
- Overriding `stream()` on the built-in `ReActLoop` so
  out-of-the-box agents emit per-token text without a custom
  strategy.
- Multi-cluster `Redlock` for `RedisSessionLock`.
- ~~Sentence-window streaming guardrails (v0.2 keeps the
  post-stream final-text check).~~ **Shipped in v0.3 polish**
  via `safety_mode: "sentence-window"`. See the v0.3
  polish subsection below.

### v0.2 follow-up — postgres + redis + slack + per-token streaming + cross-process lock + provider-aware tokeniser

Shipped on the v0.1 → v0.2 line in one PR per the user-chosen
"full v0.2 spec" scope. Eight chunks closing all six deferred
items from v0.1.

| Chunk | Commit | What landed |
|---|---|---|
| 1 | `6f4c258` | `ReasoningStrategy.stream()` non-abstract default ABC method emits one terminal `done` event (backward-compatible). New `StreamingEvent` frozen value. New `Agent.stream(task)` mirrors `Agent.run(task)` but drives the strategy via `stream()` + yields events as they arrive + emits a final canonical `done` carrying the full `RunResult` shape. `ChatSession._stream_impl` graduates: when the strategy overrides `stream()`, forwards events to wire as `ChatChunk` frames; otherwise falls back to v0.1 buffer-then-stream. |
| 2 | `952c024` | `agentforge_chat.tokenisers`: `tiktoken_tokeniser(model)` + `anthropic_tokeniser()` with lazy SDK imports + `ModuleError` remediation when missing. `TokenBudget.__init__` accepts optional `tokeniser: Tokeniser | None`; falls back to the 4-chars-per-token heuristic when None. |
| 3 | `ee99648` | New Tier-3 sister package `agentforge-chat-history-postgres`. `PostgresChatHistory.from_dsn(dsn)` opens an asyncpg pool + bootstraps schema (`CREATE TABLE IF NOT EXISTS`). Dual-table design (`chat_sessions` + `chat_turns`) with a composite index on `(session_id, timestamp)`. `PostgresRunner` Protocol + `_AsyncpgPoolRunner` production runner under `# pragma: no cover`. `PostgresFakeRunner` in `src/_inmem_runner.py` for unit tests. 100 % unit coverage on the new package. Live integration test gated by `RUN_LIVE_POSTGRES_DSN`. |
| 4 / 5 | `76f7896` | New Tier-3 sister package `agentforge-chat-history-redis` + cross-process `SessionLock` (chunks 4 + 5 combined since the lock impl lives in the redis package). `RedisChatHistory.from_url(url)` over redis-py async. Key layout: turn hash + per-session sorted set + session meta hash + sessions index set. Native TTL via `EXPIRE`. `RedisSessionLock` + `redis_session_lock_factory(runner)` use `SET NX PX` + UUID fencing + Lua unlock. `agentforge_chat._locks` extended with `SessionLock` Protocol + `InMemorySessionLock` wrapping the v0.1 `asyncio.Lock` + `default_session_lock_factory`. `ChatSession.__init__` accepts optional `session_lock_factory`. |
| 6 | `7e5f19a` | New Tier-3 sister package `agentforge-chat-slack` — Slack reference channel adapter. `SlackChatAdapter(session_factory, runner, batch_window_s)` maps `message` + `app_mention` events to `ChatSession.send`, posts a placeholder + batches `chat.update` calls every `batch_window_s` seconds with cumulative text (Slack rate-limits per channel, so per-token is impractical). `SlackRunner` Protocol + `_BoltClientRunner` production runner under `# pragma: no cover`. `FakeSlackRunner` for unit tests. Live test scaffold omitted in v0.2 (no free CI Slack workspace). |
| 7 | `1617e9a` | `.github/workflows/ci.yml` `live` job picks up the postgres + redis live suites alongside mcp + a2a. Adds a GH Actions `services:` block for Postgres + Redis on Ubuntu; macOS leaves env vars unset so service-backed tests skip cleanly. Branch protection still gates on the `test` job. |
| 8 | (this PR) | Spec §11 v0.2 follow-up + §12 runbook updates + roadmap + CHANGELOG + state. |

### v0.2 deviations from the v0.1 spec

- **Step-level / paragraph-level streaming for Slack, not
  per-token.** Slack's per-channel `chat.update` rate limit
  makes true per-token streaming impractical; the adapter
  batches every `batch_window_s` seconds.
- **`RedisSessionLock` uses single-cluster `SET NX PX` +
  UUID fencing**, not full multi-cluster Redlock. Sufficient
  for the typical chat-http deployment (1-N workers sharing
  one Redis); multi-cluster Redlock is a v0.3 follow-up.
- ~~**Output guardrails still run post-stream**, not against
  the streaming buffer. v0.2 ships the contract; sentence-
  window streaming guardrails wait for v0.3.~~ **Shipped in
  v0.3 polish** — `safety_mode: "sentence-window"` on
  `ChatSession` (or via `modules.chat.session.safety_mode`
  in YAML) buffers streamed tokens until a sentence
  boundary, runs `check_output` per completed sentence,
  and only emits the validated text downstream.
  `"stream-then-redact"` is a current alias.
- **`Agent.stream()` is a public method.** Spec §4.2 only
  documented `ChatSession.stream`; adding `Agent.stream` was
  the cleanest path to per-token chat streaming without
  bypassing pipeline + evaluator hooks.

### v0.2 out-of-scope (deferred to v0.3+)

- A2A per-token streaming via the new ABC method (separate
  feat-014 follow-up PR).
- Concrete `stream()` overrides on `ReActLoop` + the three
  experimental strategies.
- Provider-aware tokenisers for Bedrock / Vertex / Mistral
  models (one-line additions in v0.3 when first user lands).
- Migration framework for the Postgres schema.
- Multi-cluster Redlock for RedisSessionLock.

### v0.2.4 fix — session-creation contract (bug-018)

`POST /sessions` 500'd on a fresh process with the SQLite (and
Postgres / Redis) history drivers: `ChatServer._create_session`
records the session owner before the first turn, but those drivers
only inserted the session row lazily on first `append`, so
`update_session_metadata` raised `Cannot update metadata for unknown
session`. Fixed two ways, both shipped together:

- `update_session_metadata` now **upserts** the session row in every
  SQL/KV driver (create-if-missing, leaving an existing row's
  `last_active_at` untouched); the in-memory driver now lists
  metadata-only sessions.
- `ChatHistoryStore.create_session()` was added as a **concrete**
  (non-abstract) ABC method — additive to the locked contract per
  ADR-0007 — and `ChatServer` now calls it. The contract is asserted
  for every driver via the shared chat-history conformance harness.

### v0.3 polish — sentence-window streaming output guardrails

Closes the deferred safety gap from the v0.2 ship.
Per-token streaming on `ChatSession.stream()` previously
forwarded each `text` event to the wire immediately and
only ran output guardrails at end-of-stream — meaning
streamed PII / unsafe content could reach the client
before any validator saw it.

`ChatSession` now consults `safety_mode` to decide how
streamed text passes through validators:

- `"buffer-then-stream"` (default) — unchanged from v0.2.
  Agent runs to completion; output validators see the
  full text once; the assembled response is then
  sentence-segmented for the wire.
- `"sentence-window"` — streamed text accumulates in
  `_SentenceWindowBuffer`. Each push extracts completed
  sentences (`.!?` + whitespace, OR newline, OR a
  200-char hard cap). Every completed sentence runs
  through `check_output`; the validated text emits as
  the next `text` chunk. End-of-stream flushes any
  residual through the same pipeline.
- `"stream-then-redact"` — current alias for
  `sentence-window`. A future v0.3+ pass may add inline
  regex redaction without buffering.

`SafetyMode` is re-exported from `agentforge_chat`.
`build_chat_session_from_config` reads
`modules.chat.session.safety_mode` and forwards it.

## 12. Runbook

### How do I wire a chat session in code?

```python
import asyncio
from agentforge import Agent
from agentforge_chat import ChatSession, SqliteChatHistory, SlidingWindow

async def main() -> None:
    agent = Agent(model="anthropic:claude-sonnet-4-6", strategy="react")
    history = await SqliteChatHistory.from_path("./chat.db")
    session = ChatSession(
        agent=agent,
        session_id="user-42-thread-1",
        history_store=history,
        truncation=SlidingWindow(max_turns=50),
        system_prompt="You are a careful research assistant.",
        per_turn_budget_usd=0.50,
        per_session_budget_usd=10.0,
        owner="user-42",
    )
    print((await session.send("Hi")).content)
    print((await session.send("What did I just say?")).content)
    await session.close()

asyncio.run(main())
```

### How do I serve over HTTP?

```python
from agentforge import Agent
from agentforge_chat import SqliteChatHistory
from agentforge_chat_http import ChatServer, EnvBearerAuth

server = ChatServer(
    agent_factory=lambda: Agent(model="...", strategy="react"),
    history_store=await SqliteChatHistory.from_path("./chat.db"),
    auth=EnvBearerAuth("API_TOKENS"),
    host="0.0.0.0",
    port=8080,
    cors_origins=["https://chat.example.com"],
)
await server.serve()
```

Then call it: `POST /sessions` → `{id}`, `POST
/sessions/{id}/messages` with `Authorization: Bearer <token>`.
Set `Accept: text/event-stream` for SSE streaming, or open a
WebSocket at `/sessions/{id}/ws`.

### How do I wire a chat session from config?

```yaml
modules:
  chat:
    history:
      driver: sqlite
      config:
        path: ./chat.db
    truncation:
      strategy: sliding_window
      config:
        max_turns: 50
    session:
      per_turn_budget_usd: 0.50
      per_session_budget_usd: 10.0
```

```python
from agentforge_core.config import load_config
from agentforge_chat import build_chat_session_from_config
from agentforge import Agent

config = load_config()
agent = Agent(config_path=None)
session = await build_chat_session_from_config(
    config, agent, session_id="user-42", owner="user-42"
)
```

### How do I swap the history backend?

Change `modules.chat.history.driver` from `sqlite` to one of
the future v0.3 drivers (`postgres`, `redis`) and adjust the
`config:` block to the driver's accepted schema. The
`ChatHistoryStore` ABC is locked, so no application code
changes are required.

### How do I handle budget exhaustion?

`ChatSession.send()` raises
`agentforge_core.production.exceptions.BudgetExceeded` when
either `per_turn_budget_usd` or `per_session_budget_usd` would
be exceeded. The HTTP layer surfaces this as 200 + the error
captured in the response body (current behaviour); future v0.3
work will map to a clean 402-equivalent. In streaming mode,
the final chunk is `ChatChunk(kind="error",
content={"reason": "BudgetExceeded", ...})`.

### How do I test against a fake history store?

```python
from agentforge_chat import ChatSession, InMemoryChatHistory
from agentforge.testing import agent_factory, MockLLMClient

session = ChatSession(
    agent=agent_factory(model=MockLLMClient.deterministic("hi back")),
    history_store=InMemoryChatHistory(),
)
assert (await session.send("hi")).content == "hi back"
```

`run_chat_history_conformance(store)` from
`agentforge_core.testing` validates any custom store against
the locked contract.

### How do I run with Postgres history? (v0.2)

```python
from agentforge_chat_history_postgres import PostgresChatHistory

history = await PostgresChatHistory.from_dsn(
    "postgresql://user:pw@host:5432/agentforge"
)
session = ChatSession(agent=agent, history_store=history, ...)
```

`from_dsn()` opens an asyncpg pool + bootstraps the
`chat_sessions` + `chat_turns` tables idempotently
(`CREATE TABLE IF NOT EXISTS`). No migration framework in v0.2.

Capabilities: `{"ttl", "encryption_at_rest", "full_text_search"}`.

### How do I run with Redis history? (v0.2)

```python
from agentforge_chat_history_redis import RedisChatHistory

history = await RedisChatHistory.from_url(
    "redis://localhost:6379",
    ttl_seconds=86_400,  # one day; None = no expiry
)
session = ChatSession(agent=agent, history_store=history, ...)
```

Native TTL via `EXPIRE`. Capabilities:
`{"ttl", "streaming_load"}`. Trades durability for speed
relative to Postgres / SQLite — ideal for high-throughput
chat farms.

### How do I deploy chat-http behind multiple workers? (v0.2)

```python
from agentforge_chat_history_redis import (
    RedisChatHistory,
    redis_session_lock_factory,
)
from agentforge_chat_history_redis._runner import _RedisClientRunner
import redis.asyncio as redis_asyncio

client = redis_asyncio.Redis.from_url("redis://cache:6379")
runner = _RedisClientRunner(client)
history = RedisChatHistory(runner=runner)
lock_factory = redis_session_lock_factory(runner, ttl_s=30)

server = ChatServer(
    agent_factory=build_agent,
    history_store=history,
    session_lock_factory=lock_factory,
    auth=EnvBearerAuth("API_TOKENS"),
)
```

Multiple uvicorn workers behind a load balancer share the
Redis lock so the same `session_id` never runs concurrently
across pods. The Lua unlock script avoids releasing someone
else's lock if the TTL expires unexpectedly.

### How do I wire a provider-aware tokeniser? (v0.2)

```python
from agentforge_chat import TokenBudget, tiktoken_tokeniser

truncation = TokenBudget(
    max_tokens=64_000,
    tokeniser=tiktoken_tokeniser("gpt-4o-mini"),
)
session = ChatSession(agent=agent, truncation=truncation, ...)
```

Or `anthropic_tokeniser()` for Anthropic models. Both lazy-
import the backing SDK and raise `ModuleError` with pip
remediation when the SDK is missing. Falls back to the
4-chars-per-token heuristic when `tokeniser=None`.

### How do I expose this agent on Slack? (v0.2)

```python
from agentforge_chat import ChatSession
from agentforge_chat_slack import SlackChatAdapter
from agentforge_chat_slack._runner import _BoltClientRunner
from slack_sdk.web.async_client import AsyncWebClient

client = AsyncWebClient(token=os.environ["SLACK_BOT_TOKEN"])
adapter = SlackChatAdapter(
    session_factory=lambda channel_id: ChatSession(
        agent=build_agent(),
        session_id=channel_id,
    ),
    runner=_BoltClientRunner(client),
    batch_window_s=0.5,
)
await adapter.start()
```

One `ChatSession` per Slack channel ID. Streams responses
back via batched `chat.update` calls every `batch_window_s`
seconds. Slack rate-limits per channel — true per-token
isn't practical.

### How do I write a strategy that streams per-token? (v0.2)

Override `ReasoningStrategy.stream()`:

```python
from agentforge_core.contracts.strategy import ReasoningStrategy
from agentforge_core.values.chat import StreamingEvent

class MyStreamingStrategy(ReasoningStrategy):
    async def run(self, state):
        # Non-streaming path for callers that use Agent.run.
        ...
        return state

    async def stream(self, state):
        async for token in my_llm.stream(state.task):
            yield StreamingEvent(kind="text", content=token, cumulative_text=...)
        yield StreamingEvent(kind="done", content={"run_id": state.run_id})
```

`ChatSession.stream()` detects the override and forwards each
event as a `ChatChunk`. Strategies that don't override get the
ABC's default impl (one `done` after `run()` finishes) and
`ChatSession` falls back to buffer-then-stream.
