"""The meta package's extras must chain each sister package's vendor-SDK
extras (bug-015).

`pip install "agentforge-py[mcp]"` has to deliver a *working* MCP runtime,
not just the wrapper. When a sister package keeps its vendor SDK behind an
optional `[<sdk>]` extra (the lazy-import pattern), the meta extra that
points at it must request that extra — otherwise the SDK never installs and
the first call raises `ModuleError`. Conversely, a meta extra must NOT
request an extra the sister package doesn't provide (a phantom extra, e.g.
the old `agentforge-bedrock[bedrock]` when bedrock hard-deps its SDK).

This test enforces the invariant generically over every meta extra
(including `all`), so it also covers sister packages added in the future.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

# This test lives at packages/agentforge/tests/unit/ — so resolving the
# file's parents reaches the meta package dir and the packages root.
_META_PYPROJECT = Path(__file__).resolve().parents[2] / "pyproject.toml"
_PACKAGES_DIR = Path(__file__).resolve().parents[3]

_REQ_RE = re.compile(r"^\s*(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s*(?:\[(?P<extras>[^\]]*)\])?")


def _load(pyproject: Path) -> dict[str, object]:
    with pyproject.open("rb") as fh:
        return tomllib.load(fh)


def _provided_extras() -> dict[str, set[str]]:
    """Map every sister distribution name -> the set of extras it declares."""
    out: dict[str, set[str]] = {}
    for pyproject in _PACKAGES_DIR.glob("*/pyproject.toml"):
        project = _load(pyproject).get("project", {})
        assert isinstance(project, dict)
        name = project.get("name")
        if not isinstance(name, str):
            continue
        opt = project.get("optional-dependencies", {})
        out[name] = set(opt) if isinstance(opt, dict) else set()
    return out


def _parse_requirement(req: str) -> tuple[str, set[str]]:
    m = _REQ_RE.match(req)
    assert m is not None, f"unparseable requirement: {req!r}"
    extras = m.group("extras")
    requested = {e.strip() for e in extras.split(",") if e.strip()} if extras else set()
    return m.group("name"), requested


def _meta_requirements() -> list[tuple[str, str]]:
    """Every (extra_name, requirement_string) in the meta package's extras."""
    project = _load(_META_PYPROJECT).get("project", {})
    assert isinstance(project, dict)
    opt = project.get("optional-dependencies", {})
    assert isinstance(opt, dict)
    pairs: list[tuple[str, str]] = []
    for extra_name, reqs in opt.items():
        assert isinstance(reqs, list)
        for req in reqs:
            assert isinstance(req, str)
            pairs.append((extra_name, req))
    return pairs


_PROVIDED = _provided_extras()
_REQUIREMENTS = _meta_requirements()


@pytest.mark.parametrize(
    ("extra_name", "requirement"),
    _REQUIREMENTS,
    ids=[f"{e}:{r.split()[0]}" for e, r in _REQUIREMENTS],
)
def test_meta_extra_chains_sister_extras(extra_name: str, requirement: str) -> None:
    name, requested = _parse_requirement(requirement)
    if name not in _PROVIDED:
        # Not a sister package (e.g. a third-party dep) — nothing to chain.
        return
    provided = _PROVIDED[name]
    assert requested == provided, (
        f"meta extra [{extra_name}] requires {requirement!r}: it requests extras "
        f"{sorted(requested)} but {name} provides {sorted(provided)}. "
        f"A meta extra must chain exactly the sister package's vendor-SDK extras "
        f"(missing → SDK never installs; phantom → unknown-extra warning). "
        f"See bug-015."
    )


def test_invariant_actually_covers_vendor_packages() -> None:
    """Guard against the test silently passing because nothing was checked:
    at least the known vendor-SDK packages must be present in the meta extras."""
    checked = {_parse_requirement(req)[0] for _, req in _REQUIREMENTS}
    for must in ("agentforge-mcp", "agentforge-anthropic", "agentforge-ollama"):
        assert must in checked, f"{must} not referenced by any meta extra"
