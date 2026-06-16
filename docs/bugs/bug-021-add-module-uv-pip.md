---
status: fixed in 0.3.0
severity: P1
found-in: 0.2.4
found-via: agentforge-graph
---

# bug-021 — `agentforge add module` uses `python -m pip`, which is absent in uv-managed venvs

## Symptom

Running `agentforge add module <distribution>` inside an agent
scaffolded by `agentforge new` fails before installing anything:

```
$ uv run agentforge add module agentforge-memory-postgres
  → installing agentforge-memory-postgres
/path/to/.venv/bin/python: No module named pip
pip install agentforge-memory-postgres failed (exit 1)
```

The `add module` flow never reaches the manifest-apply step — the
install subprocess exits non-zero first.

## Reproduction

```bash
agentforge new my-agent      # uv-first scaffold
cd my-agent
uv sync                      # the scaffold's documented setup step
uv run agentforge add module agentforge-memory-postgres
# → "No module named pip"
```

`uv sync` creates a uv-managed virtual environment. uv deliberately
does **not** install the `pip` module into that venv, so
`python -m pip` — which `_default_pip_runner` invokes — has nothing
to run. The scaffold therefore documents a flow whose very next
step is broken: `agentforge new` is uv-first, but `add module` is
pip-first.

## Root cause

`agentforge/cli/module_cmd.py::_default_pip_runner` shells out to
the active interpreter's `pip` module:

```python
cmd = [sys.executable, "-m", "pip", *args]
```

In a uv-managed venv there is no `pip` module on the interpreter, so
`python -m pip ...` fails with "No module named pip". The scaffold
produced by `agentforge new` is uv-first (it tells users to run
`uv sync`), so the documented post-scaffold `add module` command
hits this wall every time.

## Fix

Make `_default_pip_runner` **environment-aware**: it receives
pip-style args (`["install", <dist>]` / `["uninstall", "-y", <dist>]`)
and selects the correct installer for the active environment, instead
of hard-coding one tool.

```python
if _find_uv_lock(Path.cwd()):          # uv-managed project
    cmd = ["uv", "add" if verb == "install" else "remove", dist]
elif importlib.util.find_spec("pip"):  # classic venv
    cmd = [sys.executable, "-m", "pip", *args]
else:                                  # uv venv, not a project
    cmd = ["uv", "pip", "--python", sys.executable, *args]
```

1. **uv-managed project** — a `uv.lock` exists in the cwd or any
   parent (the `_find_uv_lock` helper walks parents to the root). Use
   `uv add <dist>` / `uv remove <dist>`. These edit `pyproject.toml`
   + `uv.lock`, so the module is **persisted** as a real project
   dependency and **survives a later `uv sync`**. Plain
   `uv pip install` does not record the dependency anywhere, so a
   subsequent `uv sync` would silently uninstall the just-added
   module — the original `uv pip` fix would regress.
2. **classic venv** — no `uv.lock`, but the `pip` module is importable
   (`importlib.util.find_spec("pip")`). Use `python -m pip <args>` so
   traditional pip-managed environments keep working without requiring
   `uv` to be installed at all.
3. **uv venv that isn't a project** — no `uv.lock` and no `pip`
   module. Fall back to `uv pip --python <sys.executable> <args>`,
   which installs into the active interpreter without needing a `pip`
   module.

This keeps the uv-first scaffold (`agentforge new` → `uv sync`)
working *and* persistent, while not breaking plain pip venvs and not
hard-requiring `uv` everywhere.

The injected `pip_run` seam used by tests is unchanged, so the change
is confined to the production default runner.

## Verification

- Three unit tests in
  `packages/agentforge/tests/unit/test_module_cmd.py` monkeypatch
  `subprocess.run` (to capture the command) and control detection,
  asserting the command for each branch:
  - `test_default_pip_runner_uv_project_uses_uv_add_remove`: with a
    `uv.lock` written under `tmp_path` and `monkeypatch.chdir`, asserts
    `["uv", "add", <dist>]` for install and `["uv", "remove", <dist>]`
    for uninstall (pip's `-y` flag dropped).
  - `test_default_pip_runner_pip_available_uses_python_m_pip`: no
    `uv.lock`, `importlib.util.find_spec("pip")` patched to return a
    spec → asserts `[sys.executable, "-m", "pip", "install", <dist>]`.
  - `test_default_pip_runner_no_uv_project_no_pip_falls_back_to_uv_pip`:
    no `uv.lock`, `find_spec` patched to return `None` → asserts
    `["uv", "pip", "--python", sys.executable, "install", <dist>]`.
  The tests are deterministic (they `chdir` into `tmp_path` and patch
  `find_spec`) and do not depend on the host environment.
- **End-to-end live test** (the unit tests assert the command shape; this
  one runs it for real):
  `packages/agentforge/tests/integration/test_add_module_uv_live.py`,
  gated on `RUN_LIVE_UV=1` + `pytest.mark.live`. It builds a real
  uv-managed project, asserts the venv has **no** `pip` module (the exact
  original failure condition — `python -m pip --version` returns non-zero
  there), then runs `_default_pip_runner(["install", "six"])` and asserts
  the install succeeds, `six` is persisted to `pyproject.toml` + `uv.lock`,
  the dependency **survives a subsequent `uv sync`**, and the
  `uninstall` → `uv remove` path de-persists it. Run with:

  ```
  RUN_LIVE_UV=1 uv run pytest \
    packages/agentforge/tests/integration/test_add_module_uv_live.py -v -m live
  ```

  Verified passing against uv 0.11.12 / Python 3.13.
- `uv run pre-commit run --all-files` green (ruff, mypy --strict,
  bandit, coverage ≥ 90%).

## Notes

- A small, unrelated test-isolation fix ships alongside: an autouse
  fixture in `packages/agentforge/tests/conftest.py` strips inherited
  `GIT_DIR` / `GIT_WORK_TREE` / `GIT_INDEX_FILE`. Without it, the
  Copier-driven scaffold tests (`test_new_cmd`, `test_scaffold_state`)
  fail when the suite runs from a git hook, because the leaked
  `GIT_DIR` makes Copier mis-detect the in-repo template as a git
  remote and shell out to `git ls-remote` (exit 128). The tests pass
  outside a hook; the fixture makes them behave identically in both
  environments.
