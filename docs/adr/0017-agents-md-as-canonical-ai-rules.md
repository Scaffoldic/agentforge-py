# ADR-0017: `AGENTS.md` as canonical AI-assistant rules file

## Metadata

| Field | Value |
|---|---|
| **Number** | 0017 |
| **Title** | `AGENTS.md` as canonical AI-assistant rules file |
| **Status** | Accepted |
| **Date** | 2026-05-09 |
| **Deciders** | kjoshi |
| **Tags** | dx, ai-tooling |

---

## 1. Context and problem statement

In 2026, most agent developers code with an AI assistant alongside them
(Claude Code, Cursor, GitHub Copilot, Aider, Windsurf). Each AI tool has
its own conventions for "instructions for the assistant in this repo":
`CLAUDE.md`, `.cursorrules`, `.github/copilot-instructions.md`, and
others. Without framework-aware context, AI tools suggest patterns from
LangChain, generic Python idioms, or framework-incorrect approaches.

How do we tell every AI assistant the same set of AgentForge
conventions, without authoring N separate files that drift?

## 2. Decision drivers

- All major AI coding tools should pick up the rules without per-tool
  custom content
- One canonical file is easier to maintain than N divergent ones
- Format must be human-readable too (developer reads it on day 1)
- File must survive `agentforge upgrade` (managed file with marker
  header per ADR-0006)

## 3. Considered options

1. **`CLAUDE.md` only** — works for Claude Code, others ignored
2. **One file per tool** (`CLAUDE.md`, `.cursorrules`,
   `.github/copilot-instructions.md`, etc.) — explicit support
3. **`AGENTS.md` as canonical, thin pointers in tool-specific files** —
   AGENTS.md is the emerging tool-agnostic standard
4. **Rules embedded in source comments** — e.g. file headers describing
   conventions inline

## 4. Decision outcome

**Chosen: Option 3 — `AGENTS.md` as canonical + thin pointers.**

`AGENTS.md` at the repo root is the source of truth (~150 lines:
architecture invariants, file ownership rules, "how to add X →
runbook NN", anti-patterns, pre-commit commands). `CLAUDE.md` and
`.cursorrules` ship as thin pointers ("see `AGENTS.md`"). New AI tools
that emerge can be supported by adding their pointer file with no
content duplication.

`AGENTS.md` is a managed file (per ADR-0006); it has a
`<!-- agentforge:custom -->` fenced section the developer can add
project-specific rules to without breaking upgrades.

### Positive consequences

- One file to maintain
- Universal tool support (Claude Code, Cursor, Aider all read AGENTS.md
  per the convention)
- Developer-readable too — onboarding doc as well as AI rules
- Survives upgrades via the marker-header mechanism

### Negative consequences (trade-offs)

- AGENTS.md is an emerging standard (not yet universally adopted) —
  for tools that don't read it, the pointer files do the redirect
- Length cap (~200 lines) means runbooks must do the heavy lifting for
  detail
- AI tools may still cache outdated patterns despite `AGENTS.md`;
  documented as a residual risk

## 5. Pros and cons of the options

### Option 1: `CLAUDE.md` only

- − Other tools ignored
- − Locks framework brand to one AI vendor

### Option 2: One file per tool

- − N files to keep in sync; drift inevitable

### Option 3: AGENTS.md canonical + pointers (chosen)

- + One source of truth
- + Tool-agnostic
- + Easy to add a new tool (add a pointer)
- − Emerging standard; not every tool reads it (yet)

### Option 4: Source comments

- − AI tools don't reliably use them as project-level rules
- − Verbose per-file; not scannable

## 6. References

- [`docs/features/feat-019-developer-experience-and-ai-rules.md`](../features/feat-019-developer-experience-and-ai-rules.md)
- AGENTS.md community spec: https://agents.md
- Claude Code memory docs: https://docs.claude.com/en/docs/claude-code
- Cursor rules docs: https://docs.cursor.com/context/rules-for-ai
