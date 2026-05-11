# feat-008: Findings & output shapes

## Metadata

| Field | Value |
|---|---|
| **ID** | feat-008 |
| **Title** | Findings — `Finding` Protocol + variants (Simple, Patch, Narrative, MultiSpan) + renderers |
| **Status** | shipped (Python — `agentforge-py` PR pending merge; TypeScript pending) |
| **Owner** | kjoshi |
| **Created** | 2026-05-09 |
| **Target version** | 0.1 |
| **Languages** | both |
| **Module package(s)** | `agentforge`, `agentforge-core` (`FindingRenderer` ABC) |
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

The pain we have seen in EVA: a `Finding` dataclass with eight fixed fields,
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

---

## Implementation status

**Status: shipped (Python).** Landed across 4 chunks on
`feat/008-findings-and-output-shapes`.

| Chunk | Scope |
|---|---|
| 1 | Variants (`SimpleFinding`, `PatchFinding`, `NarrativeFinding`, `MultiSpanFinding`) + helpers (`Patch`, `Span`) as **frozen Pydantic v2 models**. Protocol-conformance + JSON round-trip + frozen-ness + field-validation tests (19 cases). |
| 2 | `FindingRenderer` ABC in `agentforge-core/contracts/renderer.py` + `RendererRegistry` in `agentforge/renderers/registry.py` with **most-specific-wins** dispatch + `MissingRendererError` (9 cases). |
| 3 | Four built-in renderers (`ScorecardRenderer`, `PatchApplierRenderer`, `MarkdownRenderer`, `SpanTableRenderer`) + `RendererRegistry.default()` factory pre-populating all four (21 cases). Each renderer supports `"text"` and `"markdown"`. |
| 4 | This Implementation section + Runbook + CHANGELOG + roadmap + forward-reference sweep + PR. |

### Deviations from this spec

- **Variants are frozen Pydantic v2 models, not `@dataclass`.** The
  spec §4.2 sketches `@dataclass`; ADR-0014 calls for frozen
  Pydantic models for value types and supersedes. Reasoning:
  findings cross persistence (`Claim.payload`), transport
  (A2A / MCP / pipeline), and LLM-output (structured-output)
  boundaries — validation on construction matters, and Pydantic
  gives JSON Schema + `model_dump` / `model_validate` round-trip
  for free. External shape is identical to the dataclass sketch.
- **`Patch` carries `hunk_count: int` field.** Not in the spec
  sketch — added so renderers (and future patch appliers) can
  produce summary stats without re-parsing the diff. Defaults to
  `1`; non-breaking.
- **`Span.end_line >= start_line` invariant enforced at
  construction** (Pydantic `@field_validator`). Spec didn't
  specify — we caught a class of impossible spans by validating.
- **`_FindingBase` internal base class** provides `to_dict()` /
  `from_dict()` plumbing. Each variant subclasses it and declares
  the three Protocol-required attributes (`severity`, `category`,
  `message`) explicitly so `isinstance(x, Finding)` resolves. Not
  exported.
- **`RendererRegistry.default()` lives on the class, not in a
  module-level builder.** Convenience for the common case.

### What's *not* yet implemented

- **`Claim.from_finding(finding, agent=...)`** helper — referenced
  in feat-005's spec §4.1 example. The helper would auto-populate
  `Claim.payload` from `Finding.to_dict()`. Out of scope here;
  tracked under feat-005 follow-up.
- **`Finding.from_dict(d)` polymorphic factory** — caller must
  know which variant they persisted today. The natural home is
  `Claim.metadata["variant"]` (or similar) when feat-005 wires
  it up.
- **HTML / JSON-LD renderers.** Per spec §9 (markdown is enough
  for v0.x); community modules can ship later.
- **Streaming finding emission** (mid-run). Per spec §9 — tasks
  emit findings; aggregation happens at end of run.
- **TypeScript port** of the whole feat-008 surface.

---

## Runbook

Audience: agent developers using AgentForge to build production
agents. Task-oriented "how do I…" content. This is the canonical
home for the feature's runbook; feat-011 / feat-019 consume these
sections into scaffolded agent projects.

### How do I emit a finding from a tool or strategy?

Pick a variant and construct it; the agent's `RunResult` carries
findings on `result.findings`:

```python
from agentforge import Agent, SimpleFinding, tool

@tool
async def lint_file(path: str) -> SimpleFinding:
    """Lint a single file and return the worst issue (if any)."""
    return SimpleFinding(
        severity="warning",
        category="style",
        message="Variable 'x' is unclear",
        file=path,
        line=42,
        recommendation="Rename to 'user_count'",
    )
```

Strategies that aggregate findings (feat-015 Pipeline, future
emit-each-step strategies) collect them into `result.findings`
automatically. Until then, return findings from tools and
aggregate in the caller.

### How do I pick a variant?

| Shape of output | Variant |
|---|---|
| One issue, one location, with an optional recommendation | `SimpleFinding` |
| Auto-fix / refactor with a structured diff | `PatchFinding` |
| Long-form prose answer with citations | `NarrativeFinding` |
| One logical issue manifested across multiple files | `MultiSpanFinding` |

If none fit — write your own. The `Finding` Protocol is
`runtime_checkable` and structural: any class with
`severity: str`, `category: str`, `message: str`, and a
`to_dict() -> dict` method satisfies it. No inheritance needed.

### How do I write a custom variant?

Subclass `_FindingBase` (recommended — you inherit `to_dict` /
`from_dict`) or a shipped variant (if extending), or write a
bare Pydantic model with the four members:

```python
from pydantic import BaseModel, ConfigDict, Field

class CoverageFinding(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)

    severity: str
    category: str = "coverage"
    message: str
    file: str
    coverage_pct: float = Field(ge=0.0, le=100.0)

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")
```

This satisfies `isinstance(x, Finding)` and persists / renders via
the same machinery as the built-ins — once you register a
renderer for it.

### How do I register a renderer for my custom variant?

```python
from agentforge import RendererRegistry, FindingRenderer

class CoverageBarRenderer(FindingRenderer):
    def render(self, finding, format="text"):
        if format == "markdown":
            return f"- **{finding.file}**: {finding.coverage_pct:.1f}%"
        return f"  {finding.file}: {finding.coverage_pct:.1f}%"

registry = RendererRegistry.default()
registry.register(CoverageFinding, CoverageBarRenderer())
```

`RendererRegistry.default()` starts with the four built-ins
already registered. Re-registering a built-in variant
(`registry.register(SimpleFinding, MyCustomScorecard())`) replaces
the built-in in place — the original registration slot is
preserved.

### How do I render a list of findings to a markdown report?

```python
from agentforge import RendererRegistry

registry = RendererRegistry.default()

def to_report(findings, format="markdown"):
    return "\n\n".join(
        registry.get(f).render(f, format=format)
        for f in findings
    )

print(to_report(result.findings))
```

Heterogeneous lists (mix of variants) work — the registry
dispatches per finding by isinstance with the most-specific-wins
rule. Custom variants subclassing a built-in variant pick up the
inherited renderer unless explicitly overridden.

### How do I persist a finding to memory?

`Finding.to_dict()` produces a JSON-compatible dict — drop it
into `Claim.payload`:

```python
from agentforge_core import Claim

claim = Claim(
    run_id=current_run().run_id,
    project="my-agent",
    agent="lint",
    category="finding",
    payload=finding.to_dict(),
)
claim_id = await memory.put(claim)
```

Round-trip: on retrieval, reconstruct via
`SimpleFinding.from_dict(claim.payload)` (or whichever variant
you persisted — feat-005 will eventually carry the variant
discriminator in `Claim.metadata` so dispatch is automatic).

### How do I debug "no renderer matched"?

`RendererRegistry.get(...)` raises `MissingRendererError` with a
remediation hint when nothing matches. Add a renderer (custom or
built-in) for the finding's type, or use
`RendererRegistry.default()` instead of an empty `RendererRegistry()`
if you forgot to populate the built-ins:

```python
# What you probably wrote:
reg = RendererRegistry()        # empty — nothing registered

# What you wanted:
reg = RendererRegistry.default() # four built-ins ready to go
```

For diagnostic introspection: `reg.registered_types()` returns
the registered types in registration order.

### How do I render different formats from the same finding?

Renderers accept a `format` argument — text and markdown are
required of every shipped renderer; custom renderers may
implement more.

```python
text  = registry.get(f).render(f, format="text")
md    = registry.get(f).render(f, format="markdown")
```

Unknown formats raise `ValueError` — fail-at-call-time, not
silently rendering as text.

### When should I NOT use a built-in variant?

- **`SimpleFinding` is too narrow** for a finding that needs
  multiple locations (use `MultiSpanFinding`) or carries a
  structured diff (use `PatchFinding`).
- **`PatchFinding` for "the LLM described a fix in prose"** —
  use `SimpleFinding` with the prose in `recommendation`. Reserve
  `PatchFinding` for actual unified diffs the consumer can apply.
- **`NarrativeFinding` for "anything that's just text"** — if
  there's a single issue / location pattern,
  `SimpleFinding(message=…)` is more discoverable than a
  body-heavy `NarrativeFinding`.
- **`MultiSpanFinding` with one span** — collapse to
  `SimpleFinding` (the renderer's per-span block is overkill for
  one location).
