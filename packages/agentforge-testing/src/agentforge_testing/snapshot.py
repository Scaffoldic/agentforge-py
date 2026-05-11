"""Approval-style snapshot helper (feat-016 chunk 4).

::

    from agentforge_testing import assert_snapshot


    def test_render() -> None:
        actual = render_my_thing()
        assert_snapshot(actual, "tests/__snapshots__/render.txt")

When the snapshot file does not exist, it is created with the
current value and the test passes. Subsequent runs compare
byte-for-byte. Pass `UPDATE_SNAPSHOTS=1` in the environment to
re-record all snapshots without modifying tests.

Mismatches surface as `SnapshotMismatch` (an `AssertionError`
subclass) so pytest reports them naturally.
"""

from __future__ import annotations

import difflib
import os
from pathlib import Path


class SnapshotMismatch(AssertionError):  # noqa: N818 — AssertionError subclass for pytest reporting
    """The actual value does not match the recorded snapshot."""


def assert_snapshot(
    actual: str,
    path: str | Path,
    *,
    update_env: str = "UPDATE_SNAPSHOTS",
) -> None:
    """Compare `actual` to the contents of `path`.

    On first run (file missing) or when the env var named by
    `update_env` is truthy, write `actual` to `path` and return
    without raising.
    """
    snapshot = Path(path)
    if os.environ.get(update_env) or not snapshot.exists():
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        snapshot.write_text(actual, encoding="utf-8")
        return
    expected = snapshot.read_text(encoding="utf-8")
    if expected != actual:
        diff = "\n".join(
            difflib.unified_diff(
                expected.splitlines(),
                actual.splitlines(),
                fromfile=str(snapshot),
                tofile="actual",
                lineterm="",
            )
        )
        msg = f"snapshot mismatch:\n{diff}"
        raise SnapshotMismatch(msg)


__all__ = ["SnapshotMismatch", "assert_snapshot"]
