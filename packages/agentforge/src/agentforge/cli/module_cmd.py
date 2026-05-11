"""`agentforge add/remove/swap module` commands (feat-010b).

These are the destructive CLI commands deferred from feat-010
PR #16. They edit `agentforge.yaml`, apply per-module manifest
files, and shell out to `pip install` / `pip uninstall`.

The pip subprocess is injected via the `pip_run` callable so tests
can mock it without actually installing packages. Production uses
`python -m pip` in the active venv.
"""

from __future__ import annotations

import argparse
import subprocess  # nosec B404
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import yaml
from agentforge_core.production.exceptions import ModuleError
from agentforge_core.values.manifest import Manifest

from agentforge.cli.manifest_apply import (
    apply_manifest,
    read_applied,
    reverse_manifest,
)

PipRunner = Callable[[Sequence[str]], int]
"""Signature: `runner(["install", "agentforge-X"]) -> exit_code`."""


def register_module_cmd(sub: argparse._SubParsersAction) -> None:  # type: ignore[type-arg]
    """Attach `agentforge add/remove/swap module` to the parent
    subparser action."""
    # `agentforge add module X` — slot into a nested `add` subparser
    # so we have room for `agentforge add tool`, etc. later.
    add = sub.add_parser("add", help="Install + wire a module into this agent.")
    add_sub = add.add_subparsers(dest="add_target", required=True)
    add_mod = add_sub.add_parser("module", help="Install + apply a module manifest.")
    add_mod.add_argument(
        "distribution", help="Module distribution (e.g. agentforge-memory-postgres)."
    )
    add_mod.set_defaults(_handler=_run_add_module)

    remove = sub.add_parser("remove", help="Remove a module from this agent.")
    remove_sub = remove.add_subparsers(dest="remove_target", required=True)
    rm_mod = remove_sub.add_parser("module", help="Reverse + uninstall a module.")
    rm_mod.add_argument("distribution", help="Module distribution to remove.")
    rm_mod.set_defaults(_handler=_run_remove_module)

    swap = sub.add_parser(
        "swap",
        help="Replace one module with another in the same category.",
    )
    swap.add_argument("category", help="Module category (memory, providers, etc.).")
    swap.add_argument("from_dist", metavar="FROM", help="Distribution to remove.")
    swap.add_argument("to_dist", metavar="TO", help="Distribution to install + apply.")
    swap.set_defaults(_handler=_run_swap)


# ----------------------------------------------------------------------
# add module
# ----------------------------------------------------------------------


def _run_add_module(
    args: argparse.Namespace,
    *,
    pip_run: PipRunner | None = None,
    cwd: Path | None = None,
    package_root: Path | None = None,
) -> int:
    """Install a module via pip + apply its manifest.

    Args:
        pip_run: Injected pip runner; defaults to `python -m pip`.
        cwd: Working directory; defaults to `Path.cwd()`.
        package_root: For tests — skip the importlib.resources lookup
            and read manifest + templates from this directory.
    """
    runner = pip_run if pip_run is not None else _default_pip_runner
    work_dir = cwd if cwd is not None else Path.cwd()
    distribution = args.distribution

    sys.stdout.write(f"  → installing {distribution}\n")
    code = runner(["install", distribution])
    if code != 0:
        sys.stderr.write(f"pip install {distribution} failed (exit {code})\n")
        return code

    try:
        manifest = _load_manifest(distribution, package_root=package_root)
    except ModuleError as exc:
        sys.stderr.write(f"manifest load failed: {exc}\n")
        return 1

    if read_applied(work_dir, distribution) is not None:
        sys.stdout.write("  → already applied (state file present); skipping\n")
        _print_next_steps(manifest)
        return 0

    try:
        apply_manifest(
            manifest,
            distribution=distribution,
            cwd=work_dir,
            package_root=package_root,
        )
    except ModuleError as exc:
        sys.stderr.write(f"manifest apply failed: {exc}\n")
        return 1

    sys.stdout.write(f"  → applied manifest for {distribution}\n")
    _print_next_steps(manifest)
    return 0


# ----------------------------------------------------------------------
# remove module
# ----------------------------------------------------------------------


def _run_remove_module(
    args: argparse.Namespace,
    *,
    pip_run: PipRunner | None = None,
    cwd: Path | None = None,
    package_root: Path | None = None,
) -> int:
    runner = pip_run if pip_run is not None else _default_pip_runner
    work_dir = cwd if cwd is not None else Path.cwd()
    distribution = args.distribution

    applied = read_applied(work_dir, distribution)
    if applied is None:
        state_dir = work_dir / ".agentforge-state"
        sys.stderr.write(
            f"No applied state for {distribution} in {state_dir}; nothing to remove.\n"
        )
        return 1

    # The reverse needs the manifest's config_block (state stores only
    # what landed, not the original block). Try to read the manifest
    # from the still-installed package; fall back to "skip config-block
    # reverse" if the package is already gone.
    config_block: dict[str, Any] = {}
    try:
        manifest = _load_manifest(distribution, package_root=package_root)
        config_block = manifest.config_block
    except ModuleError:
        # Module already uninstalled / manifest gone. Reverse what we can.
        config_block = {}

    reverse_manifest(applied, cwd=work_dir, config_block=config_block)
    sys.stdout.write(f"  → reversed manifest for {distribution}\n")

    sys.stdout.write(f"  → uninstalling {distribution}\n")
    code = runner(["uninstall", "-y", distribution])
    if code != 0:
        sys.stderr.write(f"pip uninstall {distribution} failed (exit {code})\n")
        return code
    sys.stdout.write("  → done.\n")
    return 0


# ----------------------------------------------------------------------
# swap
# ----------------------------------------------------------------------


def _run_swap(
    args: argparse.Namespace,
    *,
    pip_run: PipRunner | None = None,
    cwd: Path | None = None,
    package_root: Path | None = None,
) -> int:
    """`agentforge swap <category> <from> <to>` — remove + add atomic-ish.

    Not transactional: if `add` fails after `remove` succeeded, the
    agent is left without either module. Documented in the runbook.
    """
    # Build a fake namespace for the underlying remove + add calls.
    remove_ns = argparse.Namespace(distribution=args.from_dist)
    add_ns = argparse.Namespace(distribution=args.to_dist)
    sys.stdout.write(f"  → swap: removing {args.from_dist}, installing {args.to_dist}\n")
    code = _run_remove_module(remove_ns, pip_run=pip_run, cwd=cwd, package_root=package_root)
    if code != 0:
        return code
    return _run_add_module(add_ns, pip_run=pip_run, cwd=cwd, package_root=package_root)


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


def _load_manifest(distribution: str, *, package_root: Path | None) -> Manifest:
    """Load `<package>/manifest.yaml` for `distribution`.

    Args:
        package_root: When set, read `manifest.yaml` from this directory
            (test injection). Otherwise read via `importlib.resources`.
    """
    if package_root is not None:
        path = package_root / "manifest.yaml"
        if not path.exists():
            raise ModuleError(f"manifest.yaml not found in package_root {package_root}.")
        with path.open() as fh:
            raw = yaml.safe_load(fh) or {}
        return Manifest.model_validate(raw)

    from importlib import resources  # noqa: PLC0415 — lazy import

    package_name = distribution.replace("-", "_")
    try:
        package_files = resources.files(package_name)
    except (ModuleNotFoundError, TypeError) as exc:
        raise ModuleError(f"Cannot locate package files for {package_name!r}: {exc}.") from exc
    manifest_resource = package_files.joinpath("manifest.yaml")
    try:
        text = manifest_resource.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ModuleError(
            f"{package_name} does not ship a manifest.yaml — cannot `add` it."
        ) from exc
    raw = yaml.safe_load(text) or {}
    return Manifest.model_validate(raw)


def _print_next_steps(manifest: Manifest) -> None:
    if not manifest.next_steps:
        return
    sys.stdout.write("  Next:\n")
    for step in manifest.next_steps:
        sys.stdout.write(f"    - {step}\n")


def _default_pip_runner(args: Sequence[str]) -> int:
    """Run `python -m pip <args>` in the active venv."""
    cmd = [sys.executable, "-m", "pip", *args]
    # No untrusted input — args is built from CLI arg `distribution`
    # which is just a distribution name string. shell=False (default).
    return subprocess.run(cmd, check=False).returncode  # noqa: S603  # nosec B603
