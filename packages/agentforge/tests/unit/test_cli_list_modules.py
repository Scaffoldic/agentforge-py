"""Unit tests for `agentforge list modules` (feat-010 chunk 2).

Tests invoke `main(argv)` directly. The console-script entry point
itself is exercised by the workspace `uv sync` smoke check; we don't
run a subprocess in unit tests.
"""

from __future__ import annotations

import json
import subprocess
import sys

import pytest
from agentforge.cli.list_modules import _format_table
from agentforge.cli.main import main
from agentforge_core import Resolver, register
from agentforge_core.resolver import discover as discover_mod
from agentforge_core.resolver.discover import reset_discovery


@pytest.fixture(autouse=True)
def _resolver_snapshot():
    """Snapshot the global resolver + discovery state. Restore on
    teardown so any test that mucks with `entry_points` / `clear`
    doesn't leak into siblings."""
    resolver = Resolver.global_()
    # Trigger discovery once before snapshotting so all tests start
    # with the same fully-discovered baseline.
    resolver.list_installed()
    saved_registry = dict(resolver._registry)
    saved_module_info = dict(discover_mod._module_info_cache)
    saved_flag = discover_mod._discovered[0]
    yield
    resolver.clear()
    resolver._registry.update(saved_registry)
    discover_mod._module_info_cache.clear()
    discover_mod._module_info_cache.update(saved_module_info)
    discover_mod._discovered[0] = saved_flag


# --- argparse plumbing -------------------------------------------


def test_no_args_prints_help_and_exits_nonzero(capsys):
    with pytest.raises(SystemExit) as exc:
        main([])
    # argparse uses exit code 2 for "missing required argument".
    assert exc.value.code == 2
    out = capsys.readouterr().err
    assert "command" in out.lower()


def test_unknown_subcommand_exits_nonzero():
    with pytest.raises(SystemExit) as exc:
        main(["nonexistent"])
    assert exc.value.code == 2


def test_version_flag_works(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert capsys.readouterr().out.strip()  # non-empty version string


# --- `list modules` text output ----------------------------------


def test_list_modules_text_groups_by_category(capsys):
    code = main(["list", "modules"])
    assert code == 0
    out = capsys.readouterr().out
    # Header line for each category (uppercase).
    assert "EVALUATORS" in out
    # Entries from the workspace ship `agentforge-eval-geval`.
    assert "correctness" in out
    assert "agentforge-eval-geval" in out


def test_list_modules_category_filter(capsys):
    code = main(["list", "modules", "--category", "evaluators"])
    assert code == 0
    out = capsys.readouterr().out
    assert "EVALUATORS" in out
    # No other category headers.
    assert "MEMORY" not in out
    assert "PROVIDERS" not in out


def test_list_modules_in_process_entry_marked():
    """Classes registered via `@register` (no entry point) show
    `(in-process)` instead of a package + version."""

    @register("widgets", "thing-one")
    class _Thing:
        pass

    # Don't capture stdout here — we want to inspect the raw output
    # via the formatter directly.
    infos = Resolver.global_().list_installed(category="widgets")
    text = _format_table(infos)
    assert "thing-one" in text
    assert "(in-process)" in text


# --- `list modules` JSON output ----------------------------------


def test_list_modules_json_emits_valid_payload(capsys):
    code = main(["list", "modules", "--category", "evaluators", "--json"])
    assert code == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert isinstance(payload, list)
    assert all("category" in item and "name" in item for item in payload)
    assert {item["name"] for item in payload} >= {
        "correctness",
        "faithfulness",
        "geval",
    }


def test_list_modules_empty_registry_helpful_hint(capsys, monkeypatch):
    """When nothing is registered (after `clear`) and no entry points
    are discovered (rare — happens in completely fresh test envs),
    the output guides the user toward installing or registering."""
    Resolver.global_().clear()
    reset_discovery()
    # Patch the entry-point scan inside the discover module — that's
    # where the binding lives at runtime.
    monkeypatch.setattr(discover_mod, "entry_points", lambda: [])

    code = main(["list", "modules"])
    assert code == 0
    out = capsys.readouterr().out
    assert "No modules registered" in out
    assert "@register" in out


# --- console script smoke test (subprocess) ----------------------


def test_console_script_exists_and_runs():
    """The `[project.scripts]` entry point installed by uv works
    end-to-end."""
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "agentforge.cli.main",
            "list",
            "modules",
            "--category",
            "evaluators",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "EVALUATORS" in result.stdout
