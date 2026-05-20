"""TestPyPI dry run — mandatory pre-release step.

Builds all 34 workspace packages, uploads them to TestPyPI in
small batches (TestPyPI rate-limits aggressively), then runs a
smoke `pip install` of `agentforge-py` from TestPyPI in an
ephemeral venv and imports the runtime.

Exits 0 only if every wheel/sdist uploaded AND the smoke install
imported `agentforge.Agent` without error.

Prerequisites:

- `~/.pypirc` has a `[testpypi]` block with
  `username = __token__` and a valid TestPyPI token.
- `uv`, `python`, and `pip` are on PATH.

Usage:

    python scripts/testpypi_dry_run.py                # full run
    python scripts/testpypi_dry_run.py --skip-build   # reuse dist/
    python scripts/testpypi_dry_run.py --batch-size 5 # smaller batches
"""

from __future__ import annotations

import argparse
import configparser
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = REPO_ROOT / "dist"
SMOKE_PACKAGE = "agentforge-py[anthropic]"
DEFAULT_BATCH_SIZE = 8
RATE_LIMIT_PAUSE_SECONDS = 90


def _run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
    # All `cmd` values in this script are hardcoded literals, not user input.
    print(f"\n$ {' '.join(cmd)}")
    return subprocess.run(cmd, check=True, text=True, **kwargs)  # type: ignore[call-overload]  # noqa: S603


def _check_pypirc() -> None:
    path = Path.home() / ".pypirc"
    if not path.exists():
        sys.exit(
            f"ERROR: {path} not found. Create it with a [testpypi] block — "
            "see playbooks/publish-to-pypi.md §3.a."
        )
    cfg = configparser.ConfigParser()
    cfg.read(path)
    if "testpypi" not in cfg.sections():
        sys.exit("ERROR: ~/.pypirc has no [testpypi] section.")
    section = cfg["testpypi"]
    if section.get("username") != "__token__":
        sys.exit("ERROR: ~/.pypirc [testpypi] username must be '__token__'.")
    if not section.get("password", "").startswith("pypi-"):
        sys.exit(
            "ERROR: ~/.pypirc [testpypi] password is empty or malformed "
            "(should start with 'pypi-')."
        )


def _detect_version() -> str:
    pyproject = REPO_ROOT / "packages" / "agentforge" / "pyproject.toml"
    for line in pyproject.read_text().splitlines():
        if line.startswith("version = "):
            return line.split('"')[1]
    sys.exit("ERROR: could not detect agentforge-py version.")


def _build() -> None:
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    _run(["uv", "build", "--all"], cwd=REPO_ROOT)


def _upload_in_batches(batch_size: int) -> None:
    artefacts = sorted(p for p in DIST_DIR.iterdir() if p.suffix in {".whl", ".gz"})
    print(f"\n{len(artefacts)} artefacts to upload (batches of {batch_size}).")
    failed: list[Path] = []
    for i in range(0, len(artefacts), batch_size):
        batch = artefacts[i : i + batch_size]
        print(f"\n--- Batch {i // batch_size + 1} ({len(batch)} files) ---")
        cmd = [
            "uvx",
            "twine",
            "upload",
            "--repository",
            "testpypi",
            "--skip-existing",
            "--disable-progress-bar",
            *[str(p) for p in batch],
        ]
        try:
            subprocess.run(cmd, check=True, cwd=REPO_ROOT)  # noqa: S603
        except subprocess.CalledProcessError:
            print(
                f"WARN: batch failed (likely rate limit). "
                f"Sleeping {RATE_LIMIT_PAUSE_SECONDS}s and retrying once."
            )
            time.sleep(RATE_LIMIT_PAUSE_SECONDS)
            try:
                subprocess.run(cmd, check=True, cwd=REPO_ROOT)  # noqa: S603
            except subprocess.CalledProcessError:
                failed.extend(batch)
                print("ERROR: batch still failing after retry. Moving on.")
        if i + batch_size < len(artefacts):
            time.sleep(15)
    if failed:
        print("\nThese artefacts did not upload:")
        for p in failed:
            print(f"  - {p.name}")
        sys.exit(
            "ERROR: one or more artefacts failed to upload to TestPyPI. "
            "Wait for rate limit to clear and re-run with --skip-build."
        )


def _smoke_install(version: str) -> None:
    venv_dir = Path(tempfile.mkdtemp(prefix="agentforge-testpypi-smoke-"))
    try:
        _run(["python", "-m", "venv", str(venv_dir)])
        pip = venv_dir / "bin" / "pip"
        py = venv_dir / "bin" / "python"
        _run(
            [
                str(pip),
                "install",
                "--index-url",
                "https://test.pypi.org/simple/",
                "--extra-index-url",
                "https://pypi.org/simple/",
                f"{SMOKE_PACKAGE}=={version}",
            ]
        )
        _run([str(py), "-c", "from agentforge import Agent; print('ok')"])
    finally:
        shutil.rmtree(venv_dir, ignore_errors=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-build", action="store_true", help="reuse dist/")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()

    _check_pypirc()
    version = _detect_version()
    print(f"AgentForge TestPyPI dry run — version {version}")

    if not args.skip_build:
        _build()
    elif not DIST_DIR.exists():
        sys.exit("ERROR: --skip-build set but dist/ does not exist.")

    _upload_in_batches(args.batch_size)
    _smoke_install(version)

    print("\nTestPyPI dry run PASSED.")


if __name__ == "__main__":
    main()
