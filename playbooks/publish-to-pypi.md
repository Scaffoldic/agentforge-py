# Publish to PyPI

How to push a coordinated AgentForge release to PyPI after the
`vX.Y.Z` tag is cut and the GitHub Release is published.

> **Status (2026-05-15):** v0.2.1 in flight. The `agentforge` ↔
> `agentforge-py` rename is wired in `feat/v0.2.1-rename-and-trusted-publishing`,
> cross-package deps pinned to `~= 0.2.1`, release workflow
> shipped at `.github/workflows/release.yml`. Owner account on
> PyPI: **`scaffoldic`**. v0.2.0 stays a git-only tag; PyPI
> history begins at v0.2.1.
>
> **Auth path: hybrid.** v0.2.1 uses an API token
> (`PYPI_API_TOKEN` GitHub repo secret) to bypass the upfront
> pending-publisher registration. After v0.2.1 reserves the 34
> package names on PyPI, convert each project to Trusted
> Publishing at your own pace (see §7). End-state is full OIDC.

---

## 0. Blocker — the `agentforge` name on PyPI is taken (RESOLVED in v0.2.1)

**Resolution applied:** distribution renamed to `agentforge-py`
in v0.2.1; Python import name `agentforge` is unchanged.

The base name **`agentforge`** on PyPI is owned by an unrelated
project: [`DataBassGit/AgentForge`](https://github.com/DataBassGit/AgentForge)
v0.6.5 by John Smith / Ansel Anselmi. Sister names
(`agentforge-core`, `agentforge-anthropic`, `agentforge-openai`,
…) are all free.

### Pick one of three resolutions

| Option | What changes | Tradeoff |
|---|---|---|
| **A. Rename the runtime package** | `agentforge` → `agentforge-py` (or `scaffoldic-agentforge`, `agentforge-runtime`). Internal Python module name stays `agentforge`. | One-shot rename of one `pyproject.toml` `name` field + one CHANGELOG line. Users `pip install agentforge-py` but `from agentforge import Agent` still works. Lowest disruption. |
| **B. Negotiate the name** | Email the upstream maintainers, ask if they're willing to transfer or co-own. | Free if they say yes; weeks-of-back-and-forth + likely "no" otherwise. |
| **C. PyPI name-squatting policy** | Request name transfer from PyPI admins citing inactivity. | The squatter project is active (v0.6.5, recent updates) — request will be denied. Don't pursue. |

**Recommendation:** **Option A** — rename to `agentforge-py`.
Matches the GitHub repo slug and is unambiguous.

Verify availability:

```bash
curl -sI https://pypi.org/pypi/agentforge-py/json | head -1
# Expect: HTTP/2 404
```

Apply the rename (one line in
`packages/agentforge/pyproject.toml` + workspace source override
in root `pyproject.toml` + CHANGELOG entry). Cut v0.2.1 with the
rename or bundle it into v0.3.0 — coordinate with the release
train policy in ADR-0015.

---

## 0a. Trusted Publishing — DEFERRED (hybrid path active for v0.2.1)

**v0.2.1 publishes via API token, not OIDC.** Skip this section
for v0.2.1; come back to it any time after v0.2.1 lands and the
34 names are reserved on PyPI.

When you're ready to convert (any time, no rush), the per-project
Trusted Publisher form lives at
`https://pypi.org/manage/project/<package-name>/settings/publishing/`.
Fill the form for **each** name below. Same values for the
GitHub fields every time:

- **Owner:** `Scaffoldic`
- **Repository name:** `agentforge-py`
- **Workflow name:** `release.yml`
- **Environment name:** `pypi`

**PyPI Project Name** is the only field that changes per row:

1. `agentforge-py` ✅ (already done)
2. `agentforge-core`
3. `agentforge-bedrock`
4. `agentforge-anthropic`
5. `agentforge-openai`
6. `agentforge-voyage`
7. `agentforge-litellm`
8. `agentforge-ollama`
9. `agentforge-memory-sqlite`
10. `agentforge-memory-postgres`
11. `agentforge-memory-neo4j`
12. `agentforge-memory-surrealdb`
13. `agentforge-chat`
14. `agentforge-chat-http`
15. `agentforge-chat-history-postgres`
16. `agentforge-chat-history-redis`
17. `agentforge-chat-slack`
18. `agentforge-a2a`
19. `agentforge-mcp`
20. `agentforge-eval-geval`
21. `agentforge-testing`
22. `agentforge-otel`
23. `agentforge-langfuse`
24. `agentforge-phoenix`
25. `agentforge-evidently`
26. `agentforge-statsd`
27. `agentforge-guard-llmguard`
28. `agentforge-guard-presidio`
29. `agentforge-guard-nemo`
30. `agentforge-guard-llamaguard`
31. `agentforge-reranker-sentence-transformers`
32. `agentforge-reranker-cohere`
33. `agentforge-reranker-voyage`
34. `agentforge-reranker-mixedbread`

**34 entries total** — only needed when you convert away from
the API token. The order doesn't matter and you can do them in
batches.

Once all 34 are converted, remove `password: ${{
secrets.PYPI_API_TOKEN }}` from `release.yml` and revoke the
secret + token. OIDC takes over automatically.

---

## 0b. GitHub `pypi` environment (required either way)

Create the **`pypi` GitHub environment** at GitHub → Settings →
Environments → New environment → "pypi". Add yourself as a
required reviewer so each release run pauses for manual
approval before the upload step. This gate is the human safety
net regardless of which auth mechanism backs the upload.

---

## 1. Accounts and access

### What you need

| Account | Where | Purpose |
|---|---|---|
| **PyPI account** | <https://pypi.org/account/register/> | Production index. **Required.** |
| **TestPyPI account** | <https://test.pypi.org/account/register/> | Dry-run uploads before hitting production. **Recommended** the first time. |
| **2FA** | PyPI account settings | **Required by PyPI policy** since 2024. Use a TOTP authenticator app or a hardware key. |
| **API token** | PyPI → Account settings → API tokens → "Add API token" | Programmatic upload credential. **Required** for non-interactive `uv publish` / `twine upload`. |

### Pick the owning identity

The 16+ AgentForge packages all go under one PyPI account. Two
choices:

- **Personal account** (e.g. `kjoshi`) — fast to set up. You
  are the sole publisher; transferring later requires PyPI
  admin help.
- **Org account** (e.g. `scaffoldic`) — register a separate
  PyPI account whose username matches the GitHub org. Cleaner
  for OSS and matches the GitHub org name. Slight extra setup;
  recommended if you anticipate co-maintainers.

**Recommendation:** register `scaffoldic` on PyPI as the owning
identity, even if you're solo today. Reserves the name and
keeps personal/project credentials separate.

### Token scoping

API tokens on PyPI come in two flavours:

1. **Account-scoped token** — can upload **any** package owned
   by the account, including **brand-new package names** (i.e.
   reserve the name on first upload).
2. **Project-scoped token** — restricted to one already-existing
   project. **Cannot** create new project names.

For the first AgentForge publish, the **first upload of each
new name needs an account-scoped token** (or you must claim each
name manually via the web UI first, then mint a project-scoped
token per package). Easiest path:

1. Create one account-scoped token. Use it for the initial
   release.
2. After the first successful upload of all 16+ packages,
   **revoke the account-scoped token** and mint per-package
   project-scoped tokens for ongoing CI publishes.

Store the token in your password manager. Format:

```
pypi-AgEIcHlwaS5vcmcCJDk...  (~200 chars)
```

---

## 2. Pre-flight checks

Run these before any `uv publish`.

### a) Tag is on `main` and green

```bash
git checkout main && git pull --ff-only
git describe --tags --exact-match    # expect: vX.Y.Z
gh run list --branch main --limit 1  # expect: CI (Linux) success
```

### b) Cross-package deps are pinned

Workspace mode lets sister packages declare bare `agentforge-core`
without a version. **Built wheels inherit this**, so a user
installing `agentforge-anthropic==0.2.0` could end up with any
`agentforge-core` PyPI happens to have. Violates the ADR-0015
coordinated-release-train invariant.

Pin every cross-package dep to `~=X.Y.0`:

```bash
# Quick check:
rg '^    "agentforge(-[a-z-]+)?",?\s*$' packages/*/pyproject.toml
# Each hit needs to become:  "agentforge-core ~= 0.2.0",
```

If any are bare, open a small PR before publishing.

### c) Names available on PyPI

```bash
for pkg in $(rg -o '^name = "([^"]+)"' -r '$1' packages/*/pyproject.toml | sort -u); do
  code=$(curl -sI "https://pypi.org/pypi/$pkg/json" | head -1 | awk '{print $2}')
  echo "$code $pkg"
done
```

`404` = available (you can publish), `200` = taken (check whether
you already own it — your account page lists projects). Resolve
any unexpected `200`s before continuing.

### d) Build artefacts produce cleanly

```bash
rm -rf dist/
uv build --all
ls dist/                  # expect a .whl + .tar.gz per workspace member
```

Inspect one wheel's metadata:

```bash
unzip -p dist/agentforge_anthropic-0.2.0-py3-none-any.whl \
  agentforge_anthropic-0.2.0.dist-info/METADATA | head -40
```

Verify `Requires-Dist:` lines pin the cross-package deps.

---

## 3. Optional but recommended: TestPyPI dry run

```bash
export UV_PUBLISH_URL=https://test.pypi.org/legacy/
export UV_PUBLISH_TOKEN=pypi-AgENdGVzdC5weXBpLm9yZw...  # TestPyPI token

uv publish dist/agentforge_core-0.2.0*
uv publish dist/agentforge_anthropic-0.2.0*
# Smoke install from TestPyPI:
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            agentforge-anthropic==0.2.0
```

(TestPyPI is wiped periodically — names you reserve there don't
carry over to production PyPI.)

---

## 4. Production publish

```bash
unset UV_PUBLISH_URL                                # defaults to PyPI
export UV_PUBLISH_TOKEN=pypi-AgEIcHlwaS5vcmcC...    # production token
```

### Order of upload

`agentforge-core` first (everyone depends on it), then
`agentforge`, then sister packages in any order. PyPI is
eventually consistent — wait ~30 s between `core` and the rest
to avoid transient resolution failures during smoke installs.

```bash
# 1. core
uv publish dist/agentforge_core-0.2.0*

# 2. runtime
uv publish dist/agentforge_py-0.2.0*       # (after the rename)

# 3. all sister packages — provider, embedding, memory, chat,
#    reranker, observability, guardrails, protocol, eval, testing
uv publish dist/agentforge_anthropic-0.2.0* \
           dist/agentforge_openai-0.2.0* \
           dist/agentforge_voyage-0.2.0* \
           dist/agentforge_litellm-0.2.0* \
           dist/agentforge_ollama-0.2.0* \
           dist/agentforge_bedrock-0.2.0* \
           dist/agentforge_memory_sqlite-0.2.0* \
           dist/agentforge_memory_postgres-0.2.0* \
           dist/agentforge_memory_neo4j-0.2.0* \
           dist/agentforge_memory_surrealdb-0.2.0* \
           dist/agentforge_chat-0.2.0* \
           dist/agentforge_chat_http-0.2.0* \
           dist/agentforge_chat_history_postgres-0.2.0* \
           dist/agentforge_chat_history_redis-0.2.0* \
           dist/agentforge_chat_slack-0.2.0* \
           dist/agentforge_reranker_sentence_transformers-0.2.0* \
           dist/agentforge_reranker_cohere-0.2.0* \
           dist/agentforge_reranker_voyage-0.2.0* \
           dist/agentforge_reranker_mixedbread-0.2.0* \
           dist/agentforge_langfuse-0.2.0* \
           dist/agentforge_phoenix-0.2.0* \
           dist/agentforge_evidently-0.2.0* \
           dist/agentforge_statsd-0.2.0* \
           dist/agentforge_otel-0.2.0* \
           dist/agentforge_guard_llmguard-0.2.0* \
           dist/agentforge_guard_presidio-0.2.0* \
           dist/agentforge_guard_nemo-0.2.0* \
           dist/agentforge_guard_llamaguard-0.2.0* \
           dist/agentforge_mcp-0.2.0* \
           dist/agentforge_a2a-0.2.0* \
           dist/agentforge_eval_geval-0.2.0* \
           dist/agentforge_testing-0.2.0*
```

(34 packages total minus `agentforge-core` and the runtime
already uploaded above.)

If any upload fails partway through, **re-running on the same
version number will fail** — PyPI rejects re-uploads. Either
bump to a `.postN` (e.g. `0.2.0.post1`) or skip the
already-uploaded packages and continue.

---

## 5. Smoke verify

```bash
python -m venv /tmp/agentforge-smoke
source /tmp/agentforge-smoke/bin/activate

pip install "agentforge-anthropic[anthropic]==0.2.0"
python -c "
import asyncio
from agentforge import Agent

async def main():
    async with Agent(model='anthropic:claude-haiku-4-5-20251001') as a:
        print((await a.run('Say hi in three words.')).output)

asyncio.run(main())
"

deactivate && rm -rf /tmp/agentforge-smoke
```

Repeat with at least one package from each category:

- **Provider:** `agentforge-openai`, `agentforge-bedrock`,
  `agentforge-ollama`
- **Embedder:** `agentforge-voyage`
- **Memory:** `agentforge-memory-sqlite`
- **Reranker:** `agentforge-reranker-cohere`
- **Observability:** `agentforge-langfuse`
- **Chat history:** `agentforge-chat-history-redis`

---

## 6. Post-publish

- [ ] Revoke the account-scoped token. Mint project-scoped
      tokens for each package and store in your password
      manager.
- [ ] Update `.claude/state/current.md` `flags_for_user` —
      remove the "PyPI publish" entry.
- [ ] Append a release log entry to `.claude/state/log.md`:
      "`v0.2.0` published to PyPI (account `<owner>`); names
      reserved; tokens rotated."
- [ ] Announce on README / Discussions / blog as planned.
- [ ] Move to automation for the next release — see
      §7 below.

---

## 7. Automating future releases — Trusted Publishing

PyPI supports **OIDC Trusted Publishing** from GitHub Actions —
no long-lived API token at all. The recommended path for v0.3.0
onwards.

### One-time setup per package

1. On PyPI: go to each project → Settings → Publishing → Add
   a new pending publisher → Trusted Publisher Management.
   - Owner: `Scaffoldic`
   - Repository: `agentforge-py`
   - Workflow: `release.yml`
   - Environment (recommended): `pypi`
2. Add a `release.yml` workflow:

```yaml
name: Publish to PyPI

on:
  push:
    tags: ["v*"]

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi
    permissions:
      id-token: write
      contents: read
    steps:
      - uses: actions/checkout@v4
      - name: Install uv
        uses: astral-sh/setup-uv@v4
      - run: uv python install 3.13
      - run: uv build --all
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          packages-dir: dist/
```

3. Configure the `pypi` environment with required reviewers
   (yourself) — GitHub will block the release job until you
   click "Approve" in the Actions tab. Adds a manual gate
   before each PyPI push.

Once this is in place, **cutting a tag automatically publishes
every package** with full provenance (each artefact is signed
by the GitHub OIDC claim — visible on the PyPI project page).
Long-lived tokens can be retired.

---

## References

- [PEP 740 — Index support for digital attestations](https://peps.python.org/pep-0740/)
- [PyPA — Trusted publishers](https://docs.pypi.org/trusted-publishers/)
- [`uv publish` docs](https://docs.astral.sh/uv/guides/publish/)
- [ADR-0015 — Coordinated release train](../docs/adr/0015-coordinated-release-train.md)
- [`.claude/checklists/pre-release.md`](../.claude/checklists/pre-release.md)
