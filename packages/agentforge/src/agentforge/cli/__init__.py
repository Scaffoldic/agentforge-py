"""`agentforge` CLI (feat-010).

Read-only commands only in this PR:
- `agentforge list modules [--category <cat>]`

The destructive commands (`add`, `swap`, `remove`) edit
`agentforge.yaml` and apply a per-module `manifest.yaml`. Both
depend on feat-012 (Configuration system); they ship as a follow-
up sub-feat once that lands.

Entry point: `[project.scripts] agentforge = "agentforge.cli.main:main"`.
"""

from __future__ import annotations

from agentforge.cli.main import main

__all__ = ["main"]
