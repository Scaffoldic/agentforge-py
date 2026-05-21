---
status: open
severity: P3
found-in: v0.2.3
found-via: post-bug-007 validation via published CLI, 2026-05-21
---

# bug-008 — `_template_version` always renders `0.0.0+unknown`

## Symptom

After `agentforge new` (v0.2.3 published), the scaffolded
`.agentforge-state/answers.yml` contains:

```yaml
_template_version: 0.0.0+unknown
```

…regardless of the actually-installed framework version. Cosmetic
only — the upgrade flow (bug-007 Part B) does not require this
field — but it pollutes both the answers file and the
`AGENTFORGE-MANAGED:` marker headers that key off
`_template_version()`, e.g.

```
# AGENTFORGE-MANAGED: template:minimal@0.0.0+unknown hash:abcdef
```

Every freshly-scaffolded agent on the public PyPI install path
ships markers that lie about which framework version produced
them.

## Reproduction

```bash
pip install "agentforge-py[anthropic]==0.2.3"
agentforge new bug008-test --template minimal --provider anthropic --no-prompts
cat bug008-test/.agentforge-state/answers.yml
# → _template_version: 0.0.0+unknown   (should be 0.2.3)
head -1 bug008-test/pyproject.toml
# → # AGENTFORGE-MANAGED: template:minimal@0.0.0+unknown hash:...
```

## Root cause

`packages/agentforge/src/agentforge/cli/new_cmd.py:_template_version`:

```python
def _template_version() -> str:
    """Resolve the installed `agentforge` version — used as the
    template's `source_version` in the lock file."""
    from importlib.metadata import PackageNotFoundError, version  # noqa: PLC0415

    try:
        return version("agentforge")
    except PackageNotFoundError:  # pragma: no cover
        return "0.0.0+unknown"
```

`importlib.metadata.version()` expects the **PyPI distribution
name**, not the Python import name. AgentForge's import name is
`agentforge`, but the PyPI distribution is `agentforge-py` (this
rename shipped in v0.2.1 to dodge the squatted `agentforge` PyPI
name owned by `DataBassGit/AgentForge`). So
`version("agentforge")` raises `PackageNotFoundError` on every
PyPI-installed venv and falls through to the unknown sentinel.

For workspace-developer installs, the package is registered under
its real distribution metadata (also `agentforge-py`), so the
same lookup fails there too — but during dev, the
`PackageNotFoundError` is silent because the
`# pragma: no cover` block isn't exercised in tests.

`_template_version` has at least one second caller:
`packages/agentforge/src/agentforge/cli/_shared_scaffold.py:_framework_version`
(same incorrect lookup, same fallback). Both should be fixed
together.

## Fix

Look up by distribution name:

```python
def _template_version() -> str:
    from importlib.metadata import PackageNotFoundError, version  # noqa: PLC0415

    try:
        return version("agentforge-py")    # ← distribution name, not import name
    except PackageNotFoundError:  # pragma: no cover
        return "0.0.0+unknown"
```

Same edit in `_shared_scaffold._framework_version`. Both spots
worth a `noqa` comment naming the rename so the next bot doesn't
"fix" `"agentforge-py"` back to `"agentforge"` thinking it's a typo.

## Verification

```bash
# After fix lands + republish:
pip install "agentforge-py[anthropic]==0.2.4"
agentforge new bug008-test --template minimal --provider anthropic --no-prompts
grep "_template_version" bug008-test/.agentforge-state/answers.yml
# → _template_version: 0.2.4
head -1 bug008-test/pyproject.toml
# → # AGENTFORGE-MANAGED: template:minimal@0.2.4 hash:...
```

Add a regression test in
`packages/agentforge/tests/unit/test_new_cmd.py`:

```python
def test_scaffold_records_real_framework_version(tmp_path):
    dst = tmp_path / "agent"
    _run_new(...minimal scaffold...)
    answers = yaml.safe_load((dst / ".agentforge-state" / "answers.yml").read_text())
    assert answers["_template_version"] != "0.0.0+unknown"
    # And matches actual installed agentforge-py version:
    from importlib.metadata import version
    assert answers["_template_version"] == version("agentforge-py")
```

## Why P3 (not higher)

- Functional impact: zero. The upgrade flow (bug-007 fix) ignores
  the field; `agentforge upgrade --to <version>` works regardless.
- The lies in `AGENTFORGE-MANAGED:` marker headers are also
  cosmetic — the lock file's `source_version` carries the same
  string and would be wrong in lockstep, but neither downstream
  consumer makes decisions off them in v0.2.x.
- Will start to matter when the v0.4 `agentforge-templates`
  separate-repo migration (per bug-007 doc) lands: the
  `_template_version` will discriminate which version of the
  templates rendered a given scaffold, and Copier's actual
  three-way merge will rely on it.

Fix in v0.2.4. Not a v0.2.3 hotfix.
