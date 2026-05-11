"""`agentforge-testing` — richer test helpers (feat-016).

Pip-install:: `agentforge-testing` adds opt-in helpers that the
runtime `agentforge.testing` namespace doesn't pull in by default:

- `GoldenSetRunner.from_jsonl(...).run(agent_factory)` — load a
  JSONL fixture file, run the agent against every entry, compare
  the resulting outputs via structural diff. Exit non-zero on the
  first mismatch (or aggregate, depending on `mode`).
- `assert_snapshot(actual, path)` — Approval-style file snapshot.
  Pass `UPDATE_SNAPSHOTS=1` to re-record.
- `analyze_recording(path)` — quick stats about a cassette
  produced by `agentforge.testing.record_llm`.
"""

from __future__ import annotations

from agentforge_testing.analysis import RecordingStats, analyze_recording
from agentforge_testing.golden import (
    GoldenFixture,
    GoldenMismatch,
    GoldenResult,
    GoldenSetRunner,
)
from agentforge_testing.snapshot import (
    SnapshotMismatch,
    assert_snapshot,
)

__all__ = [
    "GoldenFixture",
    "GoldenMismatch",
    "GoldenResult",
    "GoldenSetRunner",
    "RecordingStats",
    "SnapshotMismatch",
    "analyze_recording",
    "assert_snapshot",
]
