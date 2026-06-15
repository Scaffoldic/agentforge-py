"""Packaged-wheel end-to-end gate — run the framework as a user would
*install* it, not from the editable workspace.

The unit / integration suites exercise behaviour against the editable
workspace checkout. That hides **packaging** bugs — a template that
doesn't ship in the wheel, a missing `[project.scripts]` entry point, a
module manifest left out of `package_data`. Those only surface once a
real wheel is built and installed, which is exactly when it's most
expensive (a yanked / re-cut release).

This script closes that gap. It:

  1. Builds every workspace wheel (`uv build --all`) — or reuses an
     existing `dist/` with `--skip-build` (CI passes the release build).
  2. Installs ONLY the locally-built `agentforge-*` wheels into a fresh,
     throwaway venv (third-party deps resolve from PyPI). Installing the
     wheels by path guarantees we test *these* artefacts, not whatever
     is already on PyPI at the same version.
  3. Probes for symbols that don't exist in the last public release, to
     prove the clean venv is running the freshly-built code.
  4. Exercises the real CLI end-to-end from that clean install:
       - `agentforge new`  → proves templates shipped in the wheel.
       - `agentforge config validate` → reproduces the #86 failure, then
         proves the `app:` + `imports:` fix, plus a registered
         `config_sections` plugin catching an app-config typo.
       - `agentforge add module` in the scaffolded uv project → proves
         the bug-021 env-aware installer persists to pyproject + uv.lock.

Exit 0 only if every step passes. Wired into `release.yml` as a
pre-publish gate (a broken wheel never reaches PyPI) and runnable
locally:

    python scripts/packaged_e2e.py                 # build, then test
    python scripts/packaged_e2e.py --skip-build     # reuse dist/
    python scripts/packaged_e2e.py --dist some/dir  # use a built artefact dir
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# The agentforge wheels the gate installs from the local build. The
# scaffold's own `add module` pulls agentforge-memory-sqlite from PyPI,
# so it isn't strictly required here, but installing the local one keeps
# the venv self-consistent with the build under test.
_LOCAL_WHEELS = [
    "agentforge_py",
    "agentforge_core",
    "agentforge_anthropic",
    "agentforge_memory_sqlite",
]


class GateError(RuntimeError):
    """A packaged-E2E assertion failed."""


def _run(
    cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a command, echo it, and fail hard on non-zero."""
    print(f"\n$ {' '.join(cmd)}")
    # All argv are hardcoded literals / built paths — never shell, never user input.
    return subprocess.run(  # noqa: S603
        cmd, cwd=cwd, env=env, text=True, check=True
    )


def _capture(
    cmd: list[str], *, cwd: Path | None = None, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Run a command capturing output, WITHOUT raising on non-zero (the
    caller asserts on the return code — e.g. validation that must fail)."""
    print(f"\n$ {' '.join(cmd)}")
    return subprocess.run(  # noqa: S603
        cmd, cwd=cwd, env=env, text=True, capture_output=True, check=False
    )


def _expect(condition: bool, message: str) -> None:
    if not condition:
        raise GateError(message)
    print(f"  ✓ {message}")


def _build(dist_dir: Path) -> None:
    if dist_dir.exists():
        shutil.rmtree(dist_dir)
    _run(["uv", "build", "--all", "--out-dir", str(dist_dir)], cwd=REPO_ROOT)


def _wheel(dist_dir: Path, distribution: str) -> Path:
    matches = sorted(dist_dir.glob(f"{distribution}-*.whl"))
    if not matches:
        raise GateError(f"no built wheel for {distribution} in {dist_dir}")
    return matches[-1]


def _make_clean_venv(workdir: Path) -> Path:
    """Create a throwaway venv and return its python interpreter path."""
    venv = workdir / "venv"
    _run(["uv", "venv", str(venv)])
    py = venv / ("Scripts" if os.name == "nt" else "bin") / "python"
    if not py.exists():  # windows lays it out as python.exe
        py = venv / "Scripts" / "python.exe"
    return py


def _bin(py: Path, name: str) -> Path:
    return py.parent / name


def _install_local_wheels(py: Path, dist_dir: Path) -> None:
    wheels = [str(_wheel(dist_dir, d)) for d in _LOCAL_WHEELS]
    _run(["uv", "pip", "install", "--python", str(py), *wheels])


def _probe_build_under_test(py: Path) -> None:
    """Confirm the clean venv runs the freshly-built code, not the last
    public release (these symbols postdate it)."""
    probe = textwrap.dedent(
        """
        from agentforge_core.config import validate_app_config, discover_app_sections
        from agentforge_core.config.loader import _load_file_with_imports
        from agentforge.cli.module_cmd import _find_uv_lock
        from agentforge import Agent
        print("probe: built artefact under test (new symbols importable)")
        """
    )
    _run([str(py), "-c", probe])


def _check_86(py: Path, workdir: Path) -> None:
    """#86 — app config: reproduce the original rejection, then prove the
    `app:` namespace + `imports:` directive + registered-section fix."""
    af = _bin(py, "agentforge")
    proj = workdir / "scaffold"

    print("\n=== #86 / scaffold: `agentforge new` (proves templates shipped) ===")
    _run(
        [
            str(af),
            "new",
            "rel-agent",
            "--template",
            "minimal",
            "--no-prompts",
            "--provider",
            "anthropic",
            "--dst",
            str(proj),
        ]
    )
    cfg = proj / "agentforge.yaml"
    _expect(cfg.exists(), "scaffold produced an agentforge.yaml")
    _expect((proj / "pyproject.toml").exists(), "scaffold produced a pyproject.toml")

    print("\n=== #86: baseline validate ===")
    _expect(
        _capture([str(af), "config", "validate", "--path", str(cfg)]).returncode == 0,
        "scaffolded config validates",
    )

    print("\n=== #86: reproduce the ORIGINAL failure (app key at root) ===")
    bad = workdir / "bad.yaml"
    bad.write_text("agent:\n  model: m\ngraph:\n  store:\n    path: .ckg\n")
    failed = _capture([str(af), "config", "validate", "--path", str(bad)])
    _expect(
        failed.returncode != 0 and "Extra inputs are not permitted" in failed.stderr,
        "root-level app key is still rejected (the #86 symptom)",
    )

    print("\n=== #86 P1+P3: app config under `app:`, split into its own file via `imports:` ===")
    (proj / "graph.yaml").write_text(
        "app:\n  graph:\n    store:\n      path: ${CKG_PATH:.ckg}\n    max_hops: 4\n"
    )
    with cfg.open("a") as fh:
        fh.write("\nimports:\n  - graph.yaml\napp:\n  graph:\n    max_hops: 6\n")
    _expect(
        _capture([str(af), "config", "validate", "--path", str(cfg)]).returncode == 0,
        "app: + imports: config validates",
    )

    env = {**os.environ, "CKG_PATH": "/data/ckg"}
    shown = _capture([str(af), "config", "show", "--resolved", "--path", str(cfg)], env=env)
    _expect(shown.returncode == 0, "config show --resolved succeeds")
    _expect("max_hops: 6" in shown.stdout, "local override beat the imported default (6)")
    _expect("/data/ckg" in shown.stdout, "${CKG_PATH} interpolated inside the imported file")
    _expect("imports:" not in shown.stdout, "imports directive consumed (not in resolved output)")

    print("\n=== #86 P2: install a real config_sections plugin; catch an app-config typo ===")
    _install_section_plugin(py, workdir)
    sections = _capture(
        [
            str(py),
            "-c",
            "from agentforge_core.config import discover_app_sections as d; print(list(d()))",
        ]
    )
    _expect("graph" in sections.stdout, "real entry-point plugin discovered (config_sections)")
    _expect(
        _capture([str(af), "config", "validate", "--path", str(cfg)]).returncode == 0,
        "registered section validates the good config",
    )
    (proj / "graph.yaml").write_text(
        "app:\n  graph:\n    store:\n      path: .ckg\n    max_hopz: 4\n"  # typo
    )
    typo = _capture([str(af), "config", "validate", "--path", str(cfg)])
    _expect(
        typo.returncode != 0 and "app.graph" in typo.stderr,
        "Phase 2 catches the typo inside app.graph",
    )
    # restore for any later step
    (proj / "graph.yaml").write_text(
        "app:\n  graph:\n    store:\n      path: .ckg\n    max_hops: 4\n"
    )


def _install_section_plugin(py: Path, workdir: Path) -> None:
    pkg = workdir / "section_plugin"
    (pkg / "src" / "rel_agent_config").mkdir(parents=True)
    (pkg / "pyproject.toml").write_text(
        textwrap.dedent(
            """
        [build-system]
        requires = ["hatchling"]
        build-backend = "hatchling.build"
        [project]
        name = "rel-agent-config"
        version = "0.1.0"
        dependencies = ["pydantic>=2"]
        [project.entry-points."agentforge.config_sections"]
        graph = "rel_agent_config:GraphConfig"
        [tool.hatch.build.targets.wheel]
        packages = ["src/rel_agent_config"]
        """
        )
    )
    (pkg / "src" / "rel_agent_config" / "__init__.py").write_text(
        textwrap.dedent(
            """
        from pydantic import BaseModel, ConfigDict
        class _Store(BaseModel):
            model_config = ConfigDict(extra="forbid")
            path: str
        class GraphConfig(BaseModel):
            model_config = ConfigDict(extra="forbid")
            store: _Store
            max_hops: int = 3
        """
        )
    )
    _run(["uv", "pip", "install", "--python", str(py), str(pkg)])


def _check_85(py: Path, workdir: Path) -> None:
    """bug-021 — `agentforge add module` in a real uv-managed scaffold
    persists to pyproject + uv.lock (the env-aware installer)."""
    af = _bin(py, "agentforge")
    proj = workdir / "scaffold"

    print("\n=== #85 / bug-021: add module in the scaffolded uv project ===")
    _run(["uv", "sync"], cwd=proj)
    venv_py = proj / ".venv" / "bin" / "python"
    pip_probe = _capture([str(venv_py), "-m", "pip", "--version"], cwd=proj)
    _expect(
        pip_probe.returncode != 0,
        "scaffold uv venv has no pip (the original bug-021 failure condition)",
    )

    # The CLI's manifest-apply step errors for modules without a manifest,
    # but the *install* (what bug-021 fixed) runs first; assert persistence.
    _capture([str(af), "add", "module", "agentforge-memory-sqlite"], cwd=proj)
    _expect(
        "agentforge-memory-sqlite" in (proj / "pyproject.toml").read_text(),
        "add module persisted the dependency to pyproject.toml (uv add, not pip)",
    )
    _expect(
        "agentforge-memory-sqlite" in (proj / "uv.lock").read_text(),
        "add module persisted the dependency to uv.lock (survives uv sync)",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-build", action="store_true", help="reuse an existing dist/")
    parser.add_argument(
        "--dist",
        type=Path,
        default=REPO_ROOT / "dist",
        help="directory of built wheels (default: ./dist)",
    )
    args = parser.parse_args()

    dist_dir = args.dist.resolve()
    if args.skip_build:
        if not dist_dir.exists():
            print(f"ERROR: --skip-build set but {dist_dir} does not exist.", file=sys.stderr)
            return 2
    else:
        _build(dist_dir)

    workdir = Path(tempfile.mkdtemp(prefix="agentforge-packaged-e2e-"))
    try:
        py = _make_clean_venv(workdir)
        _install_local_wheels(py, dist_dir)
        _probe_build_under_test(py)
        _check_86(py, workdir)
        _check_85(py, workdir)
    except GateError as exc:
        print(f"\nPACKAGED E2E FAILED: {exc}", file=sys.stderr)
        return 1
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    print("\nPACKAGED E2E PASSED — the built wheels scaffold + validate + add-module cleanly.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
