# feat-008: Findings & output shapes

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-008 |
| **Title** | Findings — `Finding` Protocol + variants (Simple, Patch, Narrative, MultiSpan) + renderers |
| **Status** | proposed |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.1 |
| **Languages** | both |
| **Module package(s)** | `agentforge` |
| **Depends on** | feat-001 |
| **Blocks** | feat-005 (Claim payload), feat-006 (Evaluator scores Findings) |

---

## 1. Why this feature

Agents produce different shapes of output. A code reviewer emits issues with
severity. A patch bot emits diffs. A docs Q&A agent emits prose with
citations. A compliance sweep emits multi-file findings.

Frameworks that ship one rigid output shape force everyone into it; agents
emitting prose stuff their content into a "message" field that loses
structure. Frameworks that ship no output shape force every agent to invent
one, breaking cross-agent dashboards, scorecards, and tooling.

The pain we have seen in a predecessor project: a `Finding` dataclass with eight fixed fields,
which forced patch-generating agents to misuse `metadata: dict[str, Any]` as
an escape hatch — defeating type safety and breaking downstream report
rendering.

## 2. Why it must ship as framework

- **A common contract enables shared tooling.** Aggregators, dashboards,
  CLI scorecards all consume `Finding` — they only work if every agent's
  output meets the same minimum protocol.
- **Type safety vs flexibility.** The Protocol-with-variants pattern is the
  right answer; getting it right requires careful design that shouldn't be
  redone per agent.
- **Renderers map findings to human-readable output.** A scorecard renderer
  for code review, a patch-applier for refactor bots, a markdown renderer
  for docs agents — these are reusable but only if Findings have a stable
  shape.
- **Without framework ownership:** every agent invents its own output type;
  cross-agent reporting is impossible; pipeline tasks (feat-015) can't
  generically aggregate.

## 3. How derived agents benefit

- **Pick your variant.** `SimpleFinding` for issue lists, `PatchFinding` for
  diff bots, `NarrativeFinding` for prose, `MultiSpanFinding` for
  cross-file issues. Each is a typed dataclass — `mypy` catches misuse.
- **Custom variants are first-class.** Define a domain-specific variant by
  satisfying the `Finding` Protocol; the framework treats it identically.
- **Renderer registry handles dispatch.** Pipeline emits findings; renderer
  registry looks up the right rendering function by variant; output is
  consistent.
- **Findings persist seamlessly.** `Claim.from_finding(f)` packs any
  variant into the `MemoryStore` (feat-005); querying retrieves the
  payload and reconstructs the typed object.
- **Reports for free.** A pipeline that produces 50 findings of mixed
  variants can be rendered to a markdown report with one call; the
  framework picks the right renderer per finding.

## 4. Feature specifications

### 4.1 User-facing experience

```python
from agentforge import (
    Finding, SimpleFinding, PatchFinding, NarrativeFinding, MultiSpanFinding,
    Patch, Span,
)

# Code reviewer
issue = SimpleFinding(
    severity="warning",
    category="style",
    message="Variable 'x' is unclear",
    file="src/foo.py",
    line=42,
    recommendation="Rename to 'user_count'",
)

# Patch bot
patch = PatchFinding(
    severity="suggestion",
    category="refactor",
    message="Replace deprecated `time.clock()` with `time.perf_counter()`",
    patch=Patch(file="src/timer.py", diff="@@ -1,3 +1,3 @@..."),
    rationale="`time.clock()` removed in Python 3.8",
    confidence=0.95,
)

# Docs agent
doc = NarrativeFinding(
    severity="info",
    category="answer",
    message="How does the auth flow work?",
    body="The auth flow is...\n\nKey steps:\n1...",
    references=["src/auth.py:42", "docs/auth.md"],
)

# Compliance — single issue across files
multi = MultiSpanFinding(
    severity="critical",
    category="security",
    message="Hard-coded credentials present in 3 files",
    spans=[Span(file="a.py", start_line=10, end_line=10, excerpt="API_KEY = 'abc'"),
           Span(file="b.py", start_line=22, end_line=22, excerpt="...")],
    recommendation="Move to environment variables",
)

# Custom variant — anything matching the Protocol
@dataclass
class CoverageFinding:
    severity: str
    category: str = "coverage"
    message: str = ""
    file: str = ""
    coverage_pct: float = 0.0
    def to_dict(self): return asdict(self)
```

### 4.2 Public API / contract

```python
# agentforge_core/contracts/finding.py — locked
@runtime_checkable
class Finding(Protocol):
    severity: str
    category: str
    message: str
    def to_dict(self) -> dict[str, Any]: ...

# agentforge/findings.py — shipped variants
@dataclass
class SimpleFinding:
    severity: str
    category: str
    message: str
    recommendation: str = ""
    file: str = ""
    line: int | None = None
    rule_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    def to_dict(self) -> dict[str, Any]: ...

@dataclass
class PatchFinding:
    severity: str
    category: str
    message: str
    patch: Patch                      # structured diff
    rationale: str
    confidence: float                 # 0..1
    def to_dict(self) -> dict[str, Any]: ...

@dataclass
class NarrativeFinding:
    severity: str
    category: str
    message: str
    body: str                         # markdown
    references: list[str]
    def to_dict(self) -> dict[str, Any]: ...

@dataclass
class MultiSpanFinding:
    severity: str
    category: str
    message: str
    spans: list[Span]
    recommendation: str = ""
    def to_dict(self) -> dict[str, Any]: ...

# agentforge_core/contracts/renderer.py
class FindingRenderer(ABC):
    @abstractmethod
    def render(self, finding: Finding, format: str = "text") -> str: ...
    def supports(self, finding_type: type[Finding]) -> bool: ...

# agentforge/renderers/registry.py
class RendererRegistry:
    def register(self, finding_type: type[Finding], renderer: FindingRenderer) -> None: ...
    def get(self, finding: Finding) -> FindingRenderer: ...
```

### 4.3 Internal mechanics

- Variants are plain `@dataclass` (Python) / classes (TS). They *satisfy* the
  Protocol structurally — no inheritance required.
- `RendererRegistry` does `isinstance` checks in registration order; the most
  specific match wins.
- Built-in renderers ship for each shipped variant: scorecard (Simple),
  patch-applier (Patch), markdown (Narrative), span-table (MultiSpan).
- Pipeline aggregator (feat-015) calls `RendererRegistry.get(f).render(f)`
  per finding to produce the final report.

### 4.4 Module packaging

All in `agentforge`. The Protocol definition is in `agentforge-core`; variants
+ renderers are in the runtime package.

### 4.5 Configuration

```yaml
output:
  default_finding_variant: "simple"     # for tasks that don't specify
  default_renderer: "scorecard"
  thresholds:
    fail_on: ["critical"]                # what severity blocks the run
    warn_on: ["warning", "suggestion"]
```

## 5. Plug-and-play & upgrade story

Variants and renderers are agent-defined; agents register custom renderers
without touching framework code. Adding a new shipped variant is a minor
framework bump; existing agents are unaffected because the Protocol stays
locked.

## 6. Cross-language parity

Protocol → TypeScript interface; `@dataclass` variants → typed classes.
Renderer registry identical. Built-in renderers ship in both languages at
v0.1.

## 7. Test strategy

- **Protocol conformance:** every shipped variant passes
  `isinstance(x, Finding)` runtime check.
- **Renderer dispatch:** registering for a custom variant; framework picks
  it up.
- **Round-trip:** `Finding.to_dict()` → `Claim.payload` → `from_dict()` →
  identical Finding.
- **Rendering snapshots:** locked output formats for each renderer.

## 8. Risks & open questions

| Risk / Question | Mitigation / Decision |
|---|---|
| Variants proliferate and become hard to discover | Cap shipped variants at 4 in v0.x; new variants require feature doc |
| `to_dict` round-trip ambiguity for custom types in metadata | Document JSON-serialisable rule; reject non-serialisable values at construction |
| Renderer dispatch order for inheriting variants | Most-specific class wins; document |
| Should `Finding` carry `run_id` directly? | No — `Claim` does, when persisted; `Finding` stays minimal |

## 9. Out of scope

- Visual report rendering (HTML dashboards). Out of scope; markdown is
  enough for v0.x; HTML can be a community module.
- Streaming finding emission (mid-run). Tasks emit findings; pipeline
  aggregates at end. Streaming is a future concern.
- Internationalisation of finding `message` strings. Plain text only.

## 10. References

- [`architecture.md`](../design/architecture.md) §4
- feat-001 (Agent.run returns RunResult containing findings),
  feat-005 (Claim wraps Finding payload), feat-006 (Evaluator scores Finding),
  feat-015 (Pipeline emits Findings)
- Archived: `docs/archive/cr/CR-005c-pluggable-output-shape.md`
