---
feature: none
state: idle
branch: main
started_at: null
last_milestone_at: 2026-05-12T05:30
last_shipped: feat-019 shipped via PR #23 (awaiting merge)
blocker: null
flags_for_user: []
---

## Active feature

*None — awaiting next pick.*

## Last shipped

[`feat-019 — Developer experience + AI rules`](../../docs/features/feat-019-developer-experience-and-ai-rules.md)
shipped in PR #23 with full Python scope:

- Three-section managed/custom file format
  (`split_three_section` / `merge_three_section`) so framework-
  owned documents survive upgrades with developer-owned
  customisations intact.
- `inject_shared_scaffold(dst, template_name, template_version)`
  post-render hook: walks `agentforge.templates._shared`,
  renders `.tmpl` files through Jinja, prepends marker headers,
  extends the managed-files lock.
- AGENTS.md (~115 lines) + CLAUDE.md + .cursorrules shipped in
  every scaffold. AGENTS.md covers file ownership, architecture
  invariants, runbook table, anti-patterns, pre-commit checks.
- 16 runbooks under `_shared/docs/runbooks/` (01-set-up through
  16-configuration-reference) + index README.
- `agentforge docs` CLI: list / open by stem/number/alias /
  `--check` drift / `--serve` local HTTP.

Deviations recorded in spec §10:

- Shared injection is a post-Copier step (Copier lacks clean
  cross-template `_extra_paths`).
- Modules list in AGENTS.md is empty for now (auto-populating
  from `pyproject.toml` + `modules.*` is follow-up).
- `agentforge docs --serve` uses stdlib `SimpleHTTPRequestHandler`
  (no markdown rendering).
- CI link-check deferred.
- TypeScript port deferred.

## Next pick candidates (canonical numbering)

- **feat-013** — MCP integration (consume MCP tool servers +
  expose agent tools as MCP). v0.2-target.
- **feat-015** — Pipelines & deterministic tasks (Pipeline +
  Task ABC + parallel/sequential execution). v0.2-target.
- **feat-014** — A2A (agent-to-agent) protocol support.
  v0.4-target.
- **feat-020** — Chat agents (`ChatSession` + history stores +
  HTTP/WebSocket/SSE server). v0.2-target.
- Vendor observability sub-feats (langfuse/phoenix/evidently/
  statsd).

User selects on session resume.

## Reading order on session resume

1. `AGENTS.md`
2. `.claude/CLAUDE.md`
3. `.claude/state/current.md` (this file)
4. `docs/roadmap.md` to pick next feature
