# PROGRESS: session log (append-only)

> The product is an autonomous CRE acquisition analyst. Every coding-agent session appends one entry. Never edit or delete past entries.

## Decisions
<!-- Unspecified choices made during the build, each with a one-line rationale. -->

- 2026-10-04: Owner-authorized flexibility supersedes old task path/plumbing contradictions: cross-scope build edits/new CI workflows/portable ignores, coupled-task grouping/reordering, registry-validated setup and internal improvements preserving interfaces, process corrections without weaker ACs/tests/evals, and evidence-supported analyst improvements. Source: https://app.devin.ai/sessions/70d6ca47bdbf4faf8083ca76c4988784. Existing owner guards, protected-change/CODEOWNERS review, deterministic finance/provenance, physical tenant isolation and private-eval separation remain mandatory. Routine choices are autonomous; actual owner gates remain explicit.
- 2026-10-04: Current direction excludes SEC downloads/data work and adds a licensed books/articles/reference library instead. T001 performs no sourcing or analyst work.
- 2026-10-04: Pin lightweight core libraries and dev tooling exactly; lock documented heavy/optional libraries in opt-in extras so scaffold setup does not download document models, browsers or SDK runtimes. PyPI release endpoints validated the chosen pins; plain GEPA only, never its LiteLLM extras. DBOS is excluded because v1 uses Postgres jobs.
- 2026-10-04: CLI extension convention is installed `cre_brain.**.cli`/`cli_*.py` exporting `register_cli(app)`, with explicitly named groups. Registration must be side-effect-free and import optional engines only inside commands; never discover from deal folders. Duplicate names/invalid plugins fail closed.
- 2026-10-04: Canonical scaffold seams live in domain/base (immutable TenantScope), state/base (tenant-explicit versioned store), deliverables/base (tenant-explicit finalizer), and runner/base (streaming Runner plus Policy protocols). Generics bind future T010 domain schemas without inventing duplicate Fact/Deliverable/Event models; no persistence, permission grant, finalization fallback or analyst implementation is claimed.
- 2026-10-04: `init.sh` uses installed Python 3.12 and `uv sync --locked`, installs local hooks only in its own checkout, never starts services or creates/copies `.env`; Compose DB is opt-in, project-scoped and loopback-bound. `.gitignore` excludes generated state and credentials while retaining `.env.example`.

## Needs owner
<!-- Blockers that need the owner: missing secrets, licences, spec questions. -->

## Log

### Template
```
### YYYY-MM-DD HH:MM UTC: T### <title>
- Branch: m<milestone>/<task-id>-<slug>
- Changed: <files/areas>
- Verify: <command> → exit 0
  <last 30 lines of output>
- Next: <next task id>
- Blockers: none | BLOCKED: <evidence, what is needed>
```

### 2026-10-04: Planning package created
- Docs, task list and guards specified. No code yet. Start with T001.

### 2026-10-04: Runner switched to Codex CLI; OpenHands-derived fixes
- The v1 analyst runner is the Codex CLI (`CodexRunner`). The brain is trained through it without separate model keys. Claude Agent SDK and OpenAI SDK runners move to M6 (pre-commercial).
- Policy and gates moved into the runner-agnostic `cre` tool server (MCP + CLI). OS-level limits are the primary enforcement.
- Added from the OpenHands review:
  - AgentEvent schema
  - interrupt / pause / resume / mid-task messages
  - confirm-before-act toggles (off / ask / on)
  - stuck detection
  - event redaction
  - API auth and tenant scoping
  - box agent (cre-boxd) with idempotent resume and disk-loss recovery
  - browse tool
  - parallelism limits
  - stress tests
- Blind scoring rule: the builder never acts as the analyst, and truth is materialized only after deliverables are committed.

### 2026-10-04: Adversarial review applied (pre-handoff)
- Branch model: Devin works on `dev`; each milestone is a PR `dev` → `main`; task state lives on `dev`.
- Owner-authored guards are in place before T001:
  - `CODEOWNERS` (@kavins06, to be confirmed)
  - `.github/workflows/guards.yml`
  - `scripts/protected_paths.txt` and `scripts/check_protected.py`, which read the list from the base branch; changes need the `protected-change` label
- Blind scoring is enforced physically:
  - the analyst runs in a repo-less container
  - truth is written to a separate directory
  - holdout and sealed sets live in the private repo `cre-ai-agent-evals-private` and are scored by a CI service
  - FakeRunner is plumbing only; transcripts come only from `cre record`
- Codex runner rewritten around verified behaviour:
  - the container is the sandbox
  - one throwaway extraction container per document, with no MCP
  - raw documents are not mounted for the analyst
  - pending (non-blocking) confirmations
  - API-key auth for customer data
- Learning loop:
  - no DSPy/LiteLLM; GEPA is a one-candidate proposer with a Codex LM
  - realistic budgets
  - keep-rule acceptance defined statistically
- Task list re-scoped to 71 tasks:
  - thin slice first: M2 is SCREEN + UW_MODEL through `cre run`
  - large tasks split; every AC needs a named test (`check_task.py`); approved skip markers only
- Added analyst capabilities: tax reassessment, value-add, JV waterfall, debt quotes, refi/hold-sell, rent comps (honest proxies), rent regulation, multi-deal tasks, deliverable versioning + user-edit ingestion.
- DBOS replaced by a Postgres jobs table with idempotent segments. Event `seq` is assigned by the control plane; the box uses `origin` for acks.

### 2026-10-04 05:56 UTC: T001 Repository scaffold
- Branch: `task/t001-scaffold`; integration target: `dev` only. No individual PR or main merge.
- Changed: `pyproject.toml`, `uv.lock`, `Makefile`, executable `init.sh`, `.env.example`, `docker-compose.yml`, `.gitignore`, `.pre-commit-config.yaml`; `src/cre_brain/**` package markers/CLI/domain-state-deliverable-runner contracts/`py.typed`; `brain/**` honest placeholders; `tests/test_t001_scaffold.py`, `tests/test_cli_plugins.py`, `tests/test_scaffold_contracts.py`; `AGENTS.md`, `PROGRESS.md`, only T001's `passes` in `feature_list.json`.
- Tests were written before implementations. Every AC1–AC5 has passing named tests; full offline suite: 46 passed, focused T001 suite: 33 passed. Covers installed CLI from unrelated working directories, exact pins/banned lock graph, strict tooling rejection, two real bootstrap runs in a spaced-path fresh copy, local-only Compose definition, full package layout, placeholders, environment names, plugin dispatch/fail-closed duplicate groups/root-callback protection, typed streaming Runner and tenant-explicit state/finalization seams.
- Verify: `./init.sh && make check && uv run cre --help && uv run pytest tests/test_t001_scaffold.py -q` → exit 0 in this session. Last 30 lines:
```text
    from click.utils import get_binary_stream as get_binary_stream

.venv/lib/python3.12/site-packages/typer/__init__.py:25
  /srv/infra/devin-outpost/sessions/devin-e6d731ba93854c1c863f3f8989e0e21a/workspace/repos/CRE-AI-Agent/.venv/lib/python3.12/site-packages/typer/__init__.py:25: DeprecationWarning: 'click.utils.get_text_stream' is deprecated and will be removed in Click 9.0.
    from click.utils import get_text_stream as get_text_stream

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
46 passed, 2 warnings in 4.17s

 Usage: cre [OPTIONS] COMMAND [ARGS]...

 CRE acquisition analyst brain: deterministic tools and orchestration.

╭─ Options ────────────────────────────────────────────────────────────────────╮
│ --version          Show version.                                             │
│ --help             Show this message and exit.                               │
╰──────────────────────────────────────────────────────────────────────────────╯

.................................                                        [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/typer/__init__.py:24
  /srv/infra/devin-outpost/sessions/devin-e6d731ba93854c1c863f3f8989e0e21a/workspace/repos/CRE-AI-Agent/.venv/lib/python3.12/site-packages/typer/__init__.py:24: DeprecationWarning: 'click.utils.get_binary_stream' is deprecated and will be removed in Click 9.0.
    from click.utils import get_binary_stream as get_binary_stream

.venv/lib/python3.12/site-packages/typer/__init__.py:25
  /srv/infra/devin-outpost/sessions/devin-e6d731ba93854c1c863f3f8989e0e21a/workspace/repos/CRE-AI-Agent/.venv/lib/python3.12/site-packages/typer/__init__.py:25: DeprecationWarning: 'click.utils.get_text_stream' is deprecated and will be removed in Click 9.0.
    from click.utils import get_text_stream as get_text_stream

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
33 passed, 2 warnings in 2.07s
```
- Hooks: `uv run --locked pre-commit run --all-files` → exit 0 (ruff lint/format, mypy). Initial whole-tree hook run surfaced pre-existing style in immutable `scripts/check_protected.py`; new lint hooks now target `src/` and `tests/` consistently with `make check`, tested by AC2. No guard edited or gate bypassed.
- Implementation clarification: `Runner.run_segment` is a Protocol method returning `AsyncIterator` directly, enabling async-generator implementations rather than accidentally specifying a coroutine-of-iterator. This is a typing clarification of SPEC's streaming intent; no runtime implemented.
- Existing guard files/CODEOWNERS/protected-path lists/private evals are untouched. New `gates/__init__.py` is the SPEC-mandated placeholder in a protected subtree; the eventual milestone PR still needs protected-change labeling and owner review. No task/evaluation bar relaxed.
- Next: T002 CI checks/task checker/skip markers (not started in this session).
- Blockers: none for T001. Docker unavailable on this isolated machine, so only the Compose contract was checked, not live Postgres. Two upstream Typer/Click deprecation warnings remain non-fatal. No live model, analyst run, real workbook recalculation, isolation evidence, SEC sourcing, or licensed-library ingestion is claimed.

### 2026-10-04 06:10 UTC: T001 fresh-checkout correction
- Branch: `task/t001-fresh-checkout-fix`. Stop-the-line repair before T002.
- Reproduced pre-existing baseline: 1 missing-memory import failure plus 6 missing `.cache` tmp_path setup errors. The broad `memory/` ignore excluded the source package from Git; runtime ignore is now `/memory/`. Added the missing package marker and bootstrap cache-parent creation.
- New regression archives the Git index into an empty Git checkout with a spaced path, runs bootstrap and all 33 original scaffold tests there. It never copies ignored dependencies or local source. Red run proved missing tracked memory; original assertions are unchanged.
- Verify: `./init.sh && make check && uv run cre --help && uv run pytest tests/test_t001_scaffold.py -q` → exit 0. Full suite: 47 passed. Scaffold tail:
```text
.................................                                        [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/typer/__init__.py:24
  DeprecationWarning: 'click.utils.get_binary_stream' is deprecated and will be removed in Click 9.0.

.venv/lib/python3.12/site-packages/typer/__init__.py:25
  DeprecationWarning: 'click.utils.get_text_stream' is deprecated and will be removed in Click 9.0.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
33 passed, 2 warnings in 2.22s
```
- Owner guards untouched; no feature state changes. Next: T002. Blockers: none.

### 2026-10-04 06:20 UTC: T002 CI and acceptance guards
- Branch: `task/t002-ci-guards`; integration target `dev` only.
- Changed: new `ci.yml`, `check_task.py`, `test_count.py`, `verify_features.py`, `tests/conftest.py`, and 16 behavioral guard tests. No owner-authored guard or existing assertion modified.
- Decisions: prerequisite network tests require explicit `CRE_NETWORK_ENABLED=1` rather than an unbounded network probe. Key/license markers name environment variables. Codex prerequisite uses only bounded `codex login status`, never a model call. Dynamic and collection skips/xfails fail closed unless this policy itself skipped setup for a missing approved prerequisite.
- Task checker runs fresh named tests and parses JUnit outcomes; old reports cannot supply passes. Test-count archives base and HEAD separately, collects real parametrized tests with the pinned interpreter, and fails on collection errors or count loss. Feature verification re-executes exact commands; intentionally absent from `make check` to avoid recursive verifies.
- CI: offline `check` and `test-count` on dev/main PRs, `verify-features` on main PRs and scheduled nightly; pinned tooling, Docker image save/load cache, read-only repository token. Workflow is new; existing owner guards remain intact. Protected implementation owner label/review is still required on milestone PR.
- Tests were written first (15 failures/1 defensive pass before implementation). Planted violations include missing AC, all skipped, failing AC, stale-report spoofing, marked/runtime/collection skip and xfail, lost committed test, and failing passing-feature verify.
- Verify: `make check && uv run pytest tests/test_t002_guards.py -q && uv run python scripts/check_task.py T002` → exit 0. Full suite: 63 passed. Checker tail:
```text
................                                                         [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/typer/__init__.py:24
  DeprecationWarning: 'click.utils.get_binary_stream' is deprecated and will be removed in Click 9.0.

.venv/lib/python3.12/site-packages/typer/__init__.py:25
  DeprecationWarning: 'click.utils.get_text_stream' is deprecated and will be removed in Click 9.0.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
------------ generated xml file: /tmp/cre-task-vyfqutpl/results.xml ------------
16 passed, 47 deselected, 2 warnings in 20.07s

T002: AC1 PASSED, AC2 PASSED, AC3 PASSED, AC4 PASSED, AC5 PASSED, AC6 PASSED
```
- Next: T003 configuration. Blockers: none locally; GitHub execution and owner milestone review remain separate from offline proof. No analyst-quality claims.

### 2026-10-04: Log timestamp correction
- The preceding repair/T002 headings used estimated times. The actual machine clock read `2026-10-04 06:06:21 UTC` after both integrations. The command outputs, commits and test counts are verified; those estimated heading times are not execution timestamps.

### 2026-10-04: T003 validated configuration
- Branch: `task/t003-config`; integration target `dev`.
- Added four owner YAML files, strict Pydantic settings/runner-role registry and 22 offline configuration tests. Unknown fields/roles/runners, nonpositive budgets, boolean-as-integer values, nonfinite/negative tolerances and duplicate whitelist functions fail validation. Shared-login concurrency is exactly 1.
- `load(config_dir)` uses explicit directory, otherwise `CRE_CONFIG_DIR` or cwd/config. Leaf overrides use `CRE_<SECTION>__<FIELD>` (nested role fields supported). Model/toggle overrides retain strings so YAML 1.1 cannot turn off/on into booleans. No credentials or `.env` are read into settings.
- Defaults follow SPEC: Codex owner-set models/profiles, 20-minute segments, 200 sessions/10-hour nightly limits, extraction/session concurrency 4/2. Unspecified initial reconnect timeout is 120 seconds; parity tolerance $1/1e-6, checksum/number absolute tolerance $1, number relative tolerance 1e-6, fragility margin 0.02. These are initial owner-reviewable config, not modifications of an existing protected threshold. All four action toggles default off.
- `live_enabled` uses bounded/captured `codex login status` or SDK key presence, handles missing CLI/timeout/invalid config/unknown role cleanly and never invokes a model. Tests mock all status probes and use synthetic environment values.
- Model-literal guard scans source AST outside config and catches a planted model string. Test-first red run: 19 failed before implementation. Later on/off override tests reproduced and fixed YAML boolean coercion.
- Verify: `uv run pytest tests/config -q && uv run python scripts/check_task.py T003` → exit 0; `make check` → exit 0 (85 passed; strict types/lint passed). Checker tail:
```text
......................                                                   [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/typer/__init__.py:24
  DeprecationWarning: 'click.utils.get_binary_stream' is deprecated and will be removed in Click 9.0.

.venv/lib/python3.12/site-packages/typer/__init__.py:25
  DeprecationWarning: 'click.utils.get_text_stream' is deprecated and will be removed in Click 9.0.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
------------ generated xml file: /tmp/cre-task-rht1quq9/results.xml ------------
22 passed, 63 deselected, 2 warnings in 0.58s

T003: AC1 PASSED, AC2 PASSED, AC3 PASSED, AC4 PASSED
```
- Existing owner guards/assertions unchanged. New budget/gate files need milestone protected-change label and owner review. Next: T004 replayable releases. Blockers: none for offline task verification; no live/quality/production readiness claim.

### 2026-10-04: T004 content-addressed brain releases
- Branch: `task/t004-release`; integration target `dev`.
- Added self-contained Pydantic manifests, build/list/rollback APIs, release command group and 13 offline tests. SHA-256 covers exact brain/config bytes and permissions, effective validated settings (including runner/model IDs/env overrides), gate code hash, optional bounded Codex version probe and explicitly supplied firm playbook version references.
- Snapshots contain global brain/config only. Firm contents/raw documents/private truth are never traversed. Supplied firm version references are pinned metadata, not a claim that tenant playbooks were restored.
- Decisions: deterministic manifests omit timestamps. Contents are base64 with per-file checksums to restore binary files without relying on Git. Default root is cwd; `--root` selects a checkout. `--firm-playbook-versions` accepts a JSON mapping of references. No external actions/models are invoked; CLI version/status tests are fully mocked.
- Rollback validates manifest ID/checksums, canonical allowed paths, symlinks, current gate-code identity and effective environment before modification. It replaces brain and config YAML exactly, preserving unrelated non-YAML config. It never overwrites gate code or changes environment/tenant data. Mismatched gate code requires the corresponding reviewed checkout; mismatched env requires original overrides.
- Restore stages both trees and recovers originals on installation failures/interrupts. If recovery itself fails, backups remain at the reported `.release-*` path. Offline/exclusive access is required: this is not a concurrent live-service deployment transaction. Abrupt process death can leave recovery backups; no cross-process atomicity claim.
- Cross-task plumbing correction: T001's existing discovery assertion requires an empty installed plugin list. Release is now a built-in group (`release/commands.py`) registered by the app factory. Installed plugin discovery/security checks remain unchanged; explicitly supplied plugins replace the registry for isolated factory tests. No existing test assertions were edited.
- Test-first: 11 missing-implementation errors initially. Added planted recovery-failure test, reproduced lost-backup behavior, then replaced unsafe automatic staging cleanup with backup-preserving recovery. Tests cover one-byte hash change, bytes/tree restore, runner/CLI/gate/firm identity changes, missing CLI, tampering/traversal/symlink rejection, env mismatch and restoration failure.
- Verify: `uv run pytest tests/release -q && uv run python scripts/check_task.py T004` → exit 0; `make check` → exit 0 (98 passed; lint/strict typing passed). Checker tail:
```text
.............                                                            [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/typer/__init__.py:24
  DeprecationWarning: 'click.utils.get_binary_stream' is deprecated and will be removed in Click 9.0.

.venv/lib/python3.12/site-packages/typer/__init__.py:25
  DeprecationWarning: 'click.utils.get_text_stream' is deprecated and will be removed in Click 9.0.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
------------ generated xml file: /tmp/cre-task-jhxo5dyq/results.xml ------------
13 passed, 85 deselected, 2 warnings in 0.73s

T004: AC1 PASSED, AC2 PASSED, AC3 PASSED
```
- Existing owner guards untouched. Next: M0 protected-change owner review; T010 begins M1. Blockers: none for offline verification. No SEC requests, private eval access, live models, workbook/analyst-quality/production claims.

### 2026-10-04: T002 first-milestone baseline correction
- Final all-passing-feature replay exited 0 at `1566da0`. A separate main-base test-count run exposed a legitimate edge case: documentation-only `origin/main` has no tests directory, so pytest errored instead of comparing against baseline zero.
- Branch: `task/t002-main-baseline-fix`. Treat only an absent **base** tests directory as zero. Empty HEAD and real base/HEAD collection errors still fail closed. No existing assertions weakened; two new behavioral regressions cover pre-scaffold base, empty HEAD and syntax-invalid base. New test first reproduced the failure.
- Verify: `make check && uv run pytest tests/test_t002_guards.py -q && uv run python scripts/check_task.py T002` → exit 0; full suite 100 passed. `scripts/test_count.py --base origin/main` → exit 0, `base=0 head=98` (HEAD before committing the two new tests; committed HEAD will collect 100).
```text
..................                                                       [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/typer/__init__.py:24
  DeprecationWarning: 'click.utils.get_binary_stream' is deprecated and will be removed in Click 9.0.

.venv/lib/python3.12/site-packages/typer/__init__.py:25
  DeprecationWarning: 'click.utils.get_text_stream' is deprecated and will be removed in Click 9.0.

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
------------ generated xml file: /tmp/cre-task-lor7gk92/results.xml ------------
18 passed, 82 deselected, 2 warnings in 23.51s

T002: AC1 PASSED, AC2 PASSED, AC3 PASSED, AC4 PASSED, AC5 PASSED, AC6 PASSED
```
- Feature state unchanged (T002 remains verified). Existing owner guards unchanged. Next: final M0 handoff/review. No task blockers; protected-change owner label/review remain main-promotion gates only.

### 2026-10-04: T004 M0 review hardening
- Branch `task/t004-review-hardening`: non-release JSON names no longer break listing, but a corrupt digest-named manifest still fails closed. Rollback now compares the recorded Codex CLI version before staging either tree; unavailable/installed/upgraded differences reject without writes. A no-CLI release remains restorable while offline. Four new cases first reproduced the missing guards; no existing assertions weakened.
- Local trust boundary: M0 rollback is an offline administrative operation in an operator-controlled checkout. Content addressing establishes integrity, not owner approval; untrusted seller/analyst/web release import and signing are not implemented. Documented this explicitly rather than inventing an approval credential/protocol. Evaluator/owner promotion controls remain prerequisites for distributing candidates; global analyst brain synchronization is read-only per SPEC.
- Exact T004 verification exited 0: 17 focused release tests; AC1–AC3 passed. Full `make check` exited 0 with 104 passed; Ruff/strict mypy clean.
- Next: strip pytest plugin environment overrides in T002, then replay M0. No implementation blockers; owner protected-change review remains a main-promotion gate. No services/models/credentials touched.

### 2026-10-04: T002 collection plugin isolation
- Branch `task/t002-plugin-env-hardening`: archive collection removes `PYTEST_PLUGINS`, clears `PYTEST_ADDOPTS` and forces disabled ambient entrypoint autoload. Explicitly register only the pinned asyncio, coverage and Hypothesis collection plugins; archive PYTHONPATH stays local. Current `--collect-only` needs no network/service/model plugins.
- New tests reproduce the external plugin override failure and plant an ambient entrypoint; a mutated copy with autoload enabled demonstrably fails. Pre-scaffold main still counts zero, and true base/HEAD collection errors and empty HEAD still fail.
- Exact T002 verification exited 0: full suite 106 passed; focused guards 20 passed; all AC1–AC6 passed. Existing tests/assertions and owner guard files unchanged.
- Next: resolve T004 policy approval boundary without weakening the valid historical-budget rollback test; coordinator decision pending. No daemon/host/credential changes.

### 2026-10-04: T002 verification correction
- The preceding 106/20 verification claim was premature: I integrated `fc44396` before checking the new ambient-entrypoint regression's exit. Its synthetic distribution lacked `_normalized_name`, and its ordering masked the intended poison with a duplicate explicit-plugin error. Corrected only the synthetic metadata and entrypoint order; every assertion remains unchanged. No guard behavior was removed or disabled.
- Re-ran the complete exact T002 command after that fix; exit 0. Verified task-check tail: `20 passed, 86 deselected, 2 warnings in 23.93s`; `T002: AC1 PASSED, AC2 PASSED, AC3 PASSED, AC4 PASSED, AC5 PASSED, AC6 PASSED`. The preceding chained `make check` and focused guard run also exited 0. No history rewrite.
- Coordinator now explicitly requires default policy mismatch rejection plus an action-bound operator confirmation for legitimate historical policy restoration. Next: T004 approval guard with adversarial and approved replay tests.

### 2026-10-04: T004 protected-policy confirmation
- Decision from coordinator: do not maintain a trust-history registry. Default rollback rejects gate/budget/toggle differences before staging or writes. Exact confirmation binds action + release ID + current/proposed policy digests; raw file defaults and effective settings both participate, so environment overrides cannot conceal changed defaults. CLI displays the policies and exact `--confirm-policy` token; library default is `None`. Wrong, stale and cross-release approvals fail.
- Preserved historical policy restoration only with explicit confirmation. Updated the legitimate historical-budget replay invocation to supply its exact approval as required by the new owner decision; all prior assertions, including byte-exact restore and failure recovery, remain unchanged. Brain/non-security changes require no approval. No signatures/authentication claimed; future remote control-plane exposure requires owner role and one-time action-bound approval.
- Seven new cases were first red: self-consistent gate/budget/toggle attacks, wrong/stale/action-mismatched confirmations, CLI policy display/approval, hidden-default changes, malformed YAML. All now pass, including no-write checks.
- Exact T004 verify exit 0: `24 passed, 89 deselected, 2 warnings in 1.16s`; AC1–AC3 PASSED. `make check` exit 0: `113 passed, 2 warnings in 35.62s`; Ruff/strict mypy clean. Final `verify_features.py` exit 0: all T001–T004 exact commands replayed, including T002 20 passing AC tests and T003 22 passing AC tests.
- Native `uv audit --locked` additionally reports 115 findings in the locked optional stack (MCP/PDF/Starlette), not an M0 test failure; separate core/dev audit running. Do not activate those optional stacks without coordinator dependency remediation. Audit does not suppress findings or modify the lock.
- Existing owner guard files are byte-equal to main. No main merge, protected-change bypass, live models, secrets, host edits or service starts.

### 2026-10-04: M0 core/dev dependency advisory correction
- Registry-validated dedicated correction: pytest 8.4.2 → 9.0.3 fixes CVE-2025-71176 (tmpdir handling); pytest-asyncio 1.2.0 → 1.3.0 permits pytest <10 rather than <9. Verified exact versions, Python >=3.10 metadata and plugin requirements through PyPI JSON before updating the pins and lock. No tests, assertions or skip/gate policies changed.
- Installed core/dev lock audit exit 0: `Found no known vulnerabilities and no adverse project statuses in 62 packages`. Initial core/dev findings were two advisory IDs for that single pytest CVE. No vulnerability ignores or suppressions.
- `make check` exit 0: `113 passed, 2 warnings in 39.35s`; Ruff/strict mypy clean. `verify_features.py` exit 0: all T001–T004 exact commands replayed with the new installed pins. T004 tail: `24 passed, 89 deselected, 2 warnings in 1.29s`; AC1–AC3 PASSED.
- Full optional lock audit still exits 1 with 113 advisory records in 246 packages: MCP 1.18.0 (6), pypdf 6.1.1 (95), Starlette 0.48.0 (12). These counts include alias records; they are not claims of unique exploitable defects. Coordinator explicitly owns separate optional-stack remediation before those extras/features are enabled. M0 is offline core plumbing, not production-readiness evidence.
- Reports: `.cache/m0-core-audit.log` (clean core/dev), `.cache/m0-dependency-audit-final.log` (remaining optional findings), `.cache/m0-installed-packages.json` (installed inventory), `.cache/m0-security-replay.log` (exact task replay). Next: hand off M0 once committed-source replay and review replies settle; never merge to main or bypass owner guards.

### 2026-10-04: Standing owner main-promotion authorization
- Persisted the verbatim sourced owner instruction in AGENTS.md and reconciled former blanket main-merge bans. Standing authorization permits agent promotion through the existing dev/task-branch/milestone PR flow after applicable gates pass; owner-authored guard files, protected-change label, CODEOWNERS and security/eval requirements remain unchanged. Source: https://app.devin.ai/sessions/70d6ca47bdbf4faf8083ca76c4988784.
- The preceding “never merge to main” notes described the prior permission state. For this handoff the coordinator explicitly owns promotion; this worker does not add the protected-change label or merge main.
- Committed source at 05102dc67f1d62fdaaf82a3103a5f10a1a636eb8 replayed all exact M0 task commands successfully; committed main-to-dev test count is 0→113. Core/dev native audit is clean; optional MCP/PDF/Starlette findings remain separate activation prerequisites. This final instruction-only correction does not change executable code, task flags, tests or dependencies.

### 2026-10-04: Optional dependency security prerequisites
- Dedicated coordinator branch `devin/1791097499-optional-dependency-security`: remediate the remaining 113 alias-inclusive advisory records without disabling extras or suppressing findings. Registry/release-note validated pins: pypdf 6.19.0, maintained MCP v1 1.28.1, Starlette 1.3.1 and compatible FastAPI 0.135.2. Lock changes are those four updates plus MCP's PyJWT/cryptography dependencies (and their CFFI/pycparser dependencies); no unrelated package upgrades.
- Native `uv audit --locked` exited 0: `Found no known vulnerabilities and no adverse project statuses in 250 packages`. Added a read-only, bounded dependency-audit CI workflow using native-audit-capable uv 0.12.19; existing owner guards and original test-job manager pins are unchanged. No vulnerability ignores, keys, model calls, services or task flags changed.
- `make check` exited 0: Ruff/formatting clean, strict mypy clean in 27 source files, `113 passed, 2 warnings in 37.46s`. Offline isolated probes at the exact new pins verified FastAPI request validation/content-type rejection/OpenAPI, MCP tool registration, and a generated in-memory PDF round-trip. MCP settings emitted an unresolved-forward-reference warning and Starlette TestClient deprecated httpx; future runtime tasks must validate their actual configured APIs rather than treat these minimal probes as production evidence.
- Package sources and migration references are in LIBRARY_NOTES.md. Known advisory remediation does not establish confidentiality, physical tenant isolation, safe untrusted parsing or analyst quality. Those acceptance gates remain mandatory before customer-data use. Next: independent focused dependency review, then continue licensed-library and M1 implementation.

### 2026-10-04: T010 domain schemas
- Added the frozen, extra-forbidding Pydantic v2 contracts from SPEC §4: claim/provenance/fact/assumption/calculation/question/deliverable/task/event records, all deliverable kinds, event source/kind vocabularies, version constraints and ordered date ranges. Added the minimal `GateResult(passed, failures, metrics)` contract required by both `Deliverable` and SPEC §11.
- Kept reusable Hypothesis strategies under `tests/domain/strategies.py` rather than making the development-only Hypothesis package a runtime dependency. Property coverage exercises finite Decimals, dates, booleans, Unicode strings, provenance and all event enum values through JSON serialization/validation.
- Red evidence: the new suite first failed collection because no domain models were exported. Green exact verify exit 0: `7 passed in 3.40s`; task replay `7 passed, 113 deselected, 2 warnings in 3.45s`; `T010: AC1 PASSED, AC2 PASSED, AC3 PASSED`. No model call, service, credential or external side effect was used. Next: T011 append-only SQLAlchemy/Alembic state store with genuine Postgres integration evidence plus SQLite unit coverage.
- Full `make check` exit 0 after the task-state update: Ruff and formatting clean, strict mypy clean in 28 source files, `120 passed, 2 warnings in 40.83s`.

### 2026-10-04: T010 semantic JSON round-trip correction
- Self-review strengthened the property assertion from JSON-dump equality to complete model equality. Red evidence: three failures showed a date becoming text and numeric-looking string `00123` becoming `Decimal('123')`. Wire-stability alone was insufficient evidence of lossless persistence.
- Decision: retain SPEC's Python `Decimal | str | date | bool` contract, but JSON-encode dates and Decimals as explicit `{type: date|decimal, value: string}` objects. Strings and booleans remain native JSON. The reusable value annotation applies to both facts and assumptions; validation and serialization JSON schemas include the tagged forms. Malformed/unknown tags, extra fields and non-finite numeric values fail validation.
- Official Pydantic 2.13 patterns: https://docs.pydantic.dev/latest/concepts/serialization/#field-serializers and https://docs.pydantic.dev/latest/concepts/validators/#json-schema-and-field-validators. Annotated `BeforeValidator` keeps subsequent union validation; `PlainSerializer(when_used='json')` preserves the original Python-mode types.
- Focused green: `21 passed in 3.92s`, Ruff/format clean, strict mypy clean in three domain source files. Full verify and project replay follow before integration; independent read-only review is in progress.
- Final exact verify exit 0: `21 passed in 3.81s`; task replay `21 passed, 113 deselected, 2 warnings in 4.62s`; AC1–AC3 passed. Full `make check` exit 0: strict mypy clean in 28 source files, `134 passed, 2 warnings in 45.43s`.

### 2026-10-04: Licensed public knowledge library (additional capability)
- Dedicated `task/knowledge-library`, based on accepted dev `950d6f9` (includes patched dependency commit `c63ce58`). Canonical packaged metadata catalog consolidates 42 coordinator-reviewed records into **34** works/editions: **17 DOWNLOAD_ALLOWED**, **17 REFERENCE_ONLY**. Aliases, original publication-date precision, authors/publishers, jurisdiction, rights basis, license URLs, applicability and caveats are retained. Unknown/noncommercial/contractor rights stay citation-only; no books or copyright full text in Git.
- Typed `cre_brain.knowledge` import/cache/retrieval interfaces and built-in `cre knowledge catalog/import/search` commands use one authority. Downloads default off; only exact licensed IDs/HTTPS allowlisted URLs can be fetched. Bounded DNS and IP-pinned TLS reject private/reserved/multicast destinations; no proxies/auth/credentials, redirect escape, compressed/challenge bodies or oversized PDFs. Absolute transport deadline covers slow response headers. PDF worker uses isolated Python, filtered environment, exact reviewed pypdf 6.19.0 and CPU/memory/page/text limits. Cited chunks are global-public references, never verified deal evidence, tool instructions or calculations.
- Actual online importer exercised all **17 permitted resources** with the real parser, no crawl: **15 active imports**, **1,003 physical PDF pages**, **2,419 chunks**, **18,326,737 source bytes**. **28 pages excluded** for third-party/copyright/NCMEC indicators. HUD MAP Guide (9,815,288 bytes) failed the enforced CPU budget (independent worker exit SIGXCPU); HUD EMAD returned HTTP 202 challenge. Both remain metadata fallback; no bypass, cap relaxation or fabricated import count. Live OCC reimport was `unchanged` and retained original hash/timestamp. Live DSCR/NOI, rental depreciation and CRE-concentration queries returned source/page/hash/license citations.
- Cache root is external `$XDG_DATA_HOME/cre-brain/public-knowledge` or `~/.local/share/cre-brain/public-knowledge`; no PDFs, extracted text, caches, tenant documents or datasets enter Git. Content-addressed versions retain raw-source/chunk hashes and retrieval dates; changed hashes require explicit review/activation while preserving the prior version. Atomic private files, no-follow dir-FD access, regular-file/hardlink checks and nonblocking process locks protect cache integrity. Operator-controlled retention/replay/deletion policy and same-UID/root limitations are documented in `docs/KNOWLEDGE.md`; no automated expiry or isolated production parsing claim.
- Reproducible bootstrap adds **only the already-pinned pypdf 6.19.0** to dev dependencies (one pyproject line/two lock lines), not the large documents extra. All package versions and security/audit controls remain unchanged. Built-in CLI registration preserves the existing empty-plugin discovery assertion rather than weakening tests.
- Observed verification exit 0: `./init.sh`; `make check` (Ruff/format clean, strict mypy **37 files**, **199 passed**); `uv run pytest tests/knowledge -q` (**65 passed**); `uv audit --locked` (**0 findings in 250 packages**). Tests cover rights, policies, citations, hash changes/idempotency, corrupt/budgeted PDFs, URL/DNS/redirect/type/size/time attacks, cache escape/tampering/locks, relevance/result budget, reference-only fallback, CLI and rejection as canonical `Fact`/`CalcResult`.
- `check_task.py KNOWLEDGE` exits 1 because it only accepts existing Tnnn IDs; no invented task mapping or passing feature flag. All **71 feature flags byte-unchanged from accepted dev**; no state/finance implementation, private-eval access, SEC/EDGAR/CMBS/Annex/Rule 3-14, models or host/service changes. Public-only provider is the future T032/T092 seam, not a second registry or implemented three-layer memory. Coordinator owns integration/promotion; this worker only delivers its tested task branch.
- Audited staged-source archive replay in a new virtualenv installed pypdf through plain `./init.sh`; `make check` **199 passed**, focused knowledge **65 passed**, exit 0. Initial replay lacked a Git index and correctly failed the tracked-scaffold assertion; staging only the audited archive source repaired the replay setup, with no code/assertion change. Wheel build confirmed packaged `catalog.json` and no PDFs. Pre-commit lint/format/strict-type hooks passed; staged protected-path intersection empty, feature-list byte equality verified, no source artifacts or key material staged.
- Python 3.12.14's `ipaddress` classifies public IPv4-mapped IPv6 as global/nonreserved, unlike the original VM patch release. Added explicit mapped-address refusal rather than relying on reservation classification; existing DNS attack assertion unchanged. Version-independent regression reproduced red before fix and passes after it. Reverification: `make check` **200 passed**, knowledge **66 passed**, all pre-commit hooks passed, exit 0.
- Native Python 3.12.14 audited-source replay also passed full **200** / knowledge **66** checks. Subsequently merged coordinator-accepted T011 dev `6c45a79` solely as upstream context, preserving both independent progress appendices. State/migrations/state-tests and all feature flags remain byte-equal to that accepted dev; no worker state/finance implementation or dev/main push. Combined `make check` **223 passed**, knowledge **66 passed**, native lock audit **0 findings/250 packages**, protected-path check exit 0.

### 2026-10-04: T011 append-only state store
- Added tenant-scoped SQLAlchemy tables for facts, assumptions, calculations, questions, deliverables, edges, events, jobs and corrections. Fact/deliverable histories use immutable versions with current and historical lookup; database triggers reject updates, deletes and SQLite replacement writes.
- Event ingestion assigns server-side sequences under SQLite writer locks or PostgreSQL transaction advisory locks. Origins are idempotent, conflicting replays fail closed, origin-free events remain distinct and concurrent writers receive a unique task-local sequence.
- Added Alembic upgrade/downgrade entry points and exercised them against SQLite and isolated PostgreSQL 16.15. The PostgreSQL integration test also verified history immutability and 32 concurrent event writers; `1 passed in 1.14s`.
- Exact T011 verification exited 0: `23 passed, 1 skipped, 134 deselected`; `T011: AC1 PASSED, AC2 PASSED, AC3 PASSED`. The approved integration marker skips without `CRE_TEST_DATABASE_URL`; genuine PostgreSQL evidence above used the rootless, socket-only test instance. Next: T012 dependency graph and stale propagation.

### 2026-10-04: T012 dependency graph and stale propagation
- Added tenant-scoped, duplicate-idempotent edges with deterministic topological ordering and transactional cycle refusal. SQLite writer locks and PostgreSQL tenant advisory locks serialize concurrent reciprocal inserts so exactly one succeeds; no cyclic edge is persisted.
- Rent changes invalidate only downstream calculations/artifacts, not the changed fact or unrelated nodes. Durable system `stale` events include changed/item IDs, release/runner and optional cause; all events in one invalidation share a transaction and the existing server sequence allocator. Task/tenant-filtered stale sets survive process restarts, deduplicate diamond paths and return dependencies before consumers. Repeated invalidations retain a new audit trail rather than overwriting history; rebuilding/clearing stale items is deferred to the later revision-control task.
- Red evidence: new graph tests failed first on missing module, then three propagation tests failed on missing APIs. Failure injection at the second stale event proves the first insert rolls back too. Focused exact verify exit 0: `8 passed, 1 skipped, 24 deselected`; checker AC1–AC3 passed. After licensed-library integration, exact replay: `8 passed, 1 skipped, 224 deselected`; `T012: AC1 PASSED, AC2 PASSED, AC3 PASSED`.
- Genuine isolated PostgreSQL 16.15 replay: `2 passed in 1.47s`, including unchanged T011 integration plus T012 reciprocal-cycle refusal and 32 concurrent two-event invalidations yielding task sequences 1–64. No live service, customer data or model was used. Combined `./init.sh && make check`: Ruff/format clean, strict mypy clean in 43 source files, `231 passed, 2 deselected, 2 warnings in 52.10s`. Pre-commit passed before source integration; final hooks run at task-state commit.
- Licensed library PR #2 was inspected locally and merged into the coordinator task tree after its CI passed; its source counts remain the worker's observed evidence, not a fabricated local cache claim. Only T012's feature flag changed. Next: migration-history/installed-wheel robustness review, then deterministic finance from current dependency flags. Main promotion remains subject to existing owner protected-change/CODEOWNERS gates.

### 2026-10-04: T013 rent-roll and T-12 normalization
- Added frozen Pydantic boundaries and deterministic `Decimal` calculations for rent-roll GPR, occupied-unit loss-to-lease, concessions, physical/economic occupancy and per-type unit mix. Every result maps each unit to its stored input ID; impossible rows and duplicate units fail closed rather than being silently normalized.
- Added chart-of-accounts and missing-month policy records with their own provenance IDs. T-12 normalization preserves one-time items without extrapolation, flags them individually, surfaces unmapped accounts, and supports explicit zero-fill or observed-period annualization. Missing/imputed month counts and the applied factor remain numeric outputs available to later gates.
- Decision: above-market contract rents are refused at this boundary because T013 requires both occupancy measures to stay in `[0,1]`; gain-to-lease needs a separately specified output rather than a silent clamp. One-time items are included once while recurring lines alone are annualized.
- Red evidence: both finance modules were absent and the new suite failed collection. Exact verify then exited 0: `7 passed, 233 deselected, 2 warnings`; `T013: AC1 PASSED, AC2 PASSED, AC3 PASSED`. Focused Ruff, strict mypy and all seven finance tests pass. No model, external data, service or floating-point money was used. Next: complete the independent state migration packaging repair, then T014 pro forma/tax/value-add work.

### 2026-10-04: T011 frozen, distributable migration repair
- Reproduced red: a future application table leaked into historical revision 0001, and a freshly built wheel lacked Alembic assets/failed installed-only migration; initial regression run was `3 failed, 1 passed`. Revision 0001 now owns frozen columns, keys, checks and mutation guards without importing application schema/immutability. Alembic config/environment/revision are packaged under `cre_brain.state.migrations`; the repository `migrations/alembic.ini` remains a compatible CLI entry point.
- Historical regressions explicitly target revision 0001 and assert its fixed nine-table contract, constraints and all 21 SQLite trigger definitions. Replacement predicate order is normalized only for commutative OR terms, not for missing/changed predicates. Changing live application metadata cannot change upgrade/downgrade; downgrade leaves an unrelated future table intact.
- Fresh wheel built after incorporating coordinator dev `894a900`/T013, installed with declared dependencies in an external virtualenv, and run with isolated Python `-I` from outside the checkout. Imported module/config paths were asserted under that virtualenv. SQLite and isolated rootless PostgreSQL 16.15 each passed upgrade/downgrade, all 21 immutable UPDATE/DELETE/REPLACE-or-TRUNCATE rejections and seven check/uniqueness rejections; PostgreSQL downgrade removed its guard function. Repository Alembic CLI upgrade/downgrade also passes. Only synthetic fixtures/local databases were used.
- Decision, coordinator-approved contradictory test plumbing: concurrent lock acquisition does not guarantee origin number 0 wins seq 1. Replay now selects the origin of the stored seq-1 winner; the contiguous `1..32` assertion and replay `.seq == 1` comparison are unchanged. No assertion was deleted/weakened, and production event allocation is untouched. Independent deterministic SQLite/PostgreSQL regressions force writer 1 before writer 0, prove writer 0 replays its original seq 2, and prove replay leaves the full stored history/count unchanged.
- Verification exit 0: focused repair + existing PostgreSQL suite `10 passed`; `make check` Ruff/format clean, strict mypy clean in 49 source files, `245 passed, 3 deselected, 2 warnings`. Exact task verification with local `CRE_TEST_DATABASE_URL` (Typer/Click deprecation warnings omitted from this displayed tail):
  ```text
  ......................................                                   [100%]
  38 passed, 3 deselected in 5.58s
  .................................                                        [100%]
  33 passed, 215 deselected, 2 warnings in 5.38s
  T011: AC1 PASSED, AC2 PASSED, AC3 PASSED
  ```
- All pre-commit lint/format/strict-type hooks passed. All existing feature flags, finance source/tests, graph/event production code and protected files remain byte-unchanged relative to coordinator dev. No private evaluation/source data, models, credentials or production deployment. Next: push only the repair task branch for coordinator review/real PostgreSQL replay; coordinator owns dev integration and explicitly releases the group. Blockers: none; awaiting coordinator integration feedback.

### 2026-10-04: T013 account namespace follow-up
- A synthetic adversarial probe demonstrated a mapped category named `unmapped:other` merging its amount with an actually unmapped `other` account. Chart boundaries now reject the reserved `unmapped:` line prefix, retaining the existing output contract and all prior assertions. The new regression failed before the validator and passes afterward.
- Fresh exact T013 verify exited 0: `8 passed, 233 deselected, 2 warnings`; `T013: AC1 PASSED, AC2 PASSED, AC3 PASSED`. `make check` exited 0: lint/format/strict types clean, `239 passed, 2 deselected, 2 warnings in 52.58s`. No feature flag changed. Next: independent finance review and migration repair, then T014. Main promotion still requires the existing owner protected-change label/review; private evals and live services untouched.

### 2026-10-04: T013 caller-independent arithmetic
- Independent review confirmed that ambient Decimal precision changes actual money, not only formatting. Tests first reproduced changed rent-roll/T-12 results, caller-triggered Inexact/Rounded exceptions, and caller exponent-limit Overflow: `4 failed, 1 passed`. The shared private calculation wrapper now supplies every Context field explicitly, preserving standard 28-significant-digit half-even arithmetic while rejecting invalid operations, division by zero, overflow and accidental float operations. No cent quantization or new financial assumptions were introduced.
- Every calculation gets an isolated context copy and restores its caller even on failure. Six new regressions cover low/high precision, alternate rounding, traps, exponent limits, caller flags/state preservation, and a mutated DefaultContext. Source: https://docs.python.org/3.12/library/decimal.html#decimal.localcontext and https://docs.python.org/3.12/library/decimal.html#decimal.Context (unspecified constructor fields otherwise inherit mutable defaults).
- Exact T013 verification exited 0 in this session:
  ```text
  ..............                                                           [100%]
  14 passed in 0.65s
  ..............                                                           [100%]
  14 passed, 233 deselected, 2 warnings in 1.15s
  T013: AC1 PASSED, AC2 PASSED, AC3 PASSED
  ```
- Focused Ruff/format/strict types pass. Full `make check` exited 0: `245 passed, 2 deselected, 2 warnings in 53.64s`; source lint/format/strict types clean. Existing assertions and feature flags are unchanged. Migration repair is independently accepted and separately integrated at `e88ca8f`; this finance branch awaits fresh review and combined-dev replay before the next group release. No model calls, private eval access or live-service changes. Next: T014 pro forma/taxes/value-add using the same calculation policy.

### 2026-10-04: T013 combined integration replay
- Combined the independently accepted frozen migration repair `e88ca8f`, account namespace correction `f29af7d`, and caller-independent arithmetic `8e85cda`. The only merge conflict was concurrent progress appendices; all three evidence sections are retained. No source/test assertion conflict and no feature flag or protected guard change.
- Fresh independent arithmetic review accepted `8e85cda`: exact T013 verifier, focused lint/format/strict types, 15 hostile context configurations, 64 threaded callers, poisoned DefaultContext before import, nested calls and validation/arithmetic failures. Original precision-28 monetary outputs, provenance, caller identity/flags/traps and global defaults are preserved; no blocking findings remain. Separate frozen/packaged migration review accepted installed-wheel SQLite/PostgreSQL execution and historical schema immutability.
- Coordinator replay on the combined staged tree exited 0, with pytest commands serialized to avoid the repository's shared basetemp collision:
  ```text
  make check: Ruff/format clean, strict mypy clean in 50 source files
  252 passed, 3 deselected, 2 warnings in 62.65s
  uv run pytest tests/state -q: 41 passed in 6.63s (isolated PostgreSQL 16.15 included)
  T011: 33 passed, 222 deselected; AC1 PASSED, AC2 PASSED, AC3 PASSED
  T013: 14 passed, 241 deselected; AC1 PASSED, AC2 PASSED, AC3 PASSED
  T012: 9 passed, 246 deselected; AC1 PASSED, AC2 PASSED, AC3 PASSED
  ```
- No missing-integration claim: three integration tests excluded from `make check` were separately executed successfully against the rootless/socket-only fixture; credentials stayed in its native passfile. Main PR #1 remains open/mergeable with four passing checks and the owner protected-change guard failure, no labels or owner review. No bypass, private-eval access, model calls or live-service changes. Next: release the workflow group from current tested dev, then T014 operating projections/tax/value-add.

### 2026-10-04: T012 stale-event ULID wire-contract repair
- Replaced `uuid4().hex` in graph-generated stale events with canonical 26-character Crockford Base32 ULIDs per SPEC §4. Each ID encodes the same UTC millisecond timestamp as its event plus 80 bits from `secrets.token_bytes(10)`. Existing tenant locks, event sequencing, graph order, payloads and transaction boundaries are unchanged.
- Red-first evidence: all seven new offline ULID/entropy cases failed against UUID generation. Regression coverage inspects real persisted events at the Unix epoch, a sub-millisecond boundary and Python's maximum datetime; repeated same-millisecond invalidations and 32 concurrent two-event invalidations retain distinct IDs and contiguous sequences. Controlled zero/all-one entropy proves the full 80-bit field; failure on the second entropy request rolls back the first event too. Separate PostgreSQL coverage checks persisted canonical IDs and decoded timestamps under concurrent invalidation. Existing tests/assertions are retained.
- Decisions: no shared ULID generator/dependency exists, so use the standard library in the allowed graph module without a lockfile change. Integer timedelta division avoids float timestamp rounding; six-byte unsigned conversion fails closed for out-of-range timestamps. IDs use the ordinary random ULID variant, not a process-local monotonic counter; durable server-assigned `seq` remains authoritative for same-millisecond ordering.
- Exact verify command: `uv run pytest tests/state -q -k graph && uv run python scripts/check_task.py T012`. Exit **0**, with `CRE_TEST_DATABASE_URL` bound to a disposable PostgreSQL 16.15 cluster. Verification output tail (the command produced fewer than 30 lines):
  ```text
  .................                                                        [100%]
  17 passed, 32 deselected in 3.97s

  .................                                                        [100%]
  =============================== warnings summary ===============================
  .venv/lib/python3.12/site-packages/typer/__init__.py:24
    /srv/infra/devin-outpost/sessions/devin-0dbd21040b5a41bcad9430277ed910e6/workspace/repos/CRE-AI-Agent/.venv/lib/python3.12/site-packages/typer/__init__.py:24: DeprecationWarning: 'click.utils.get_binary_stream' is deprecated and will be removed in Click 9.0.
      from click.utils import get_binary_stream as get_binary_stream

  .venv/lib/python3.12/site-packages/typer/__init__.py:25
    /srv/infra/devin-outpost/sessions/devin-0dbd21040b5a41bcad9430277ed910e6/workspace/repos/CRE-AI-Agent/.venv/lib/python3.12/site-packages/typer/__init__.py:25: DeprecationWarning: 'click.utils.get_text_stream' is deprecated and will be removed in Click 9.0.
      from click.utils import get_text_stream as get_text_stream

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  17 passed, 246 deselected, 2 warnings in 3.32s

  T012: AC1 PASSED, AC2 PASSED, AC3 PASSED
  ```
- `make check` exit 0: Ruff/format clean in 76 files, strict mypy clean in 50 source files, `259 passed, 4 deselected, 2 warnings in 55.42s`. `uv run pre-commit run --all-files` exit 0. PostgreSQL integration file separately exited 0 (`3 passed in 1.81s`), including existing T011 migration/state semantics and T012 concurrency/cycle checks.
- Complete state-area replay with the same disposable PostgreSQL fixture exited 0: `49 passed in 7.49s`, including the fourth integration test excluded from `make check` and all earlier state regressions.
- The cluster was extracted locally from the PostgreSQL apt package under ignored `.cache`, initialized/run in a user namespace and restricted to this session's Unix socket with TCP disabled. Initial abstract-socket attempts failed in psycopg hostname resolution; switching only the disposable fixture to a regular session-specific socket resolved it without production/test-policy changes.
- Inherited T012 `passes: true` is freshly reverified; no feature flag changed. Owner guards, protected paths, dependencies and unrelated source remain unchanged. No live services, customer data, private evaluations, model calls or Excel runtime were used; this is state/wire-contract evidence, not analyst-quality evidence. Next: integrate this tested repair into dev for coordinator review, then T014 operating projections/tax/value-add. Blockers: none.

### 2026-10-04: T031 local Docker sandbox and physical isolation
- Added the typed `SandboxProvider`/`Box`/`ExecResult` contract and trusted `LocalDockerProvider`. Analyst containers run non-root with read-only rootfs, dropped capabilities, no-new-privileges, memory/CPU/PID limits, tenant-labelled private volumes and no Docker socket. Only deals, memory, outbox and scratch are writable; sleep/resume retain named volumes. Foreign resource collisions are rejected without deletion.
- Reference Ubuntu images install pinned Codex/uv, Python, CRE runtime, LibreOffice/UNO/unoserver, Chromium/Playwright and fonts. Extractors receive only a bounded parsed JSON object, read-only, plus disposable scratch; no raw documents, analyst memory, skills or MCP configuration. Runtime credentials enter individual exec environments, never image layers/container config. Transfers use no-follow path traversal, bounded regular files and atomic replacement; snapshots reject symlinks/hardlinks, credential filenames and known credential values.
- Egress uses a dedicated sidecar network namespace with deny-by-default iptables. UID 1000 may reach only the loopback CONNECT proxy; UID 1001 may use public DNS and HTTPS. The proxy requires exact domains, rejects all non-public/multicast/reserved answers and connects to the validated numeric address. Setup capabilities are irrevocably dropped before handling requests. No privileged analyst or host-network container is used.
- Decisions: default resources implement SPEC's 2 CPU / 4 GB single-session minimum; owners provision at least 20 GB persistent disk and storage quotas, and configure 4 CPU / 8 GB for two sessions. Trusted host orchestration is the extraction sidecar API, not a daemon socket in the analyst. Known-secret snapshot refusal is not arbitrary encoded-secret detection. These local fixtures prove OS/plumbing behavior, not live analyst quality.
- Red/runtime evidence: the mount-source delimiter regression failed before its boundary validator (`DID NOT RAISE`); physical validation caught root initialization traversal permissions, a read-only resolver write, missing Python alias, COPY permissions under restrictive host umask, and Docker's empty-volume copy-up resetting ownership. Fixed with startup-only initialization capabilities, a read-only sidecar DNS bind, explicit interpreter/file permissions and volume-nocopy on writable volumes. Chromium now actually launches and renders an isolated title. Peer-network assertions require an observed listening server before attempting access.
- All reference images built in a disposable Docker 28.3.3 daemon with separate data/socket and mount/network namespaces under ignored session-local `.cache`; no shared daemon/service was changed. Docker was initially absent, so this substitutes a real isolated daemon, never a host-process sandbox or mocked OS tests. Synthetic credential sentinels only; no model calls, customer data or private evaluation access.
- Initial exact verification passed with explicitly built `cre-box:t031`/`cre-extract:t031`. Final verification below also exercised fresh-runner bootstrap: only `DOCKER_HOST=unix:///tmp/cre-t031-420/socket` and `CRE_SANDBOX_DOCKER=$PWD/.cache/docker-runtime/docker/docker` were supplied. The physical integration fixture builds default reference images once per pytest process using a credential-free client environment, so existing main/nightly feature verification needs no guard/CI changes. Explicit owner image overrides are never rebuilt. Final commands were serialized to avoid pytest basetemp collisions. Output tail (existing Typer/Click deprecation warnings omitted):
  ```text
  uv run pytest tests/sandbox -q
  ............................                                             [100%]
  28 passed in 141.98s (0:02:21)

  uv run python scripts/check_task.py T031
  .........                                                                [100%]
  9 passed, 282 deselected, 2 warnings in 47.18s
  T031: AC1 PASSED, AC2 PASSED, AC3 PASSED, AC4 PASSED

  make check
  All checks passed!
  85 files already formatted
  Success: no issues found in 54 source files
  280 passed, 11 deselected, 2 warnings in 58.56s

  uv run pre-commit run --all-files
  ruff lint................................................................Passed
  ruff format..............................................................Passed
  strict source types......................................................Passed
  ```
- Review: checked correctness, simplicity, protocol/image boundaries, bounded operations and tenant/secret/egress safety; ownership preflight and mount-source delimiter regressions added. No existing assertion/guard or other task flag changed; only T031 becomes true after fresh verification. Reusable `python -m tests.sandbox.contract --factory module:factory --image IMAGE` executes policy-disabled shell isolation against an owner's real provider.
- Final host-transfer review reproduced a symlink-ancestor escape in a failing regression. Host upload, download, and extraction reads now reuse the bounded, file-descriptor-based no-follow helper from the filesystem root, rejecting symlink ancestors and avoiding check-then-unbounded-read races. The regression also verifies downloads cannot create nested directories through a symlink ancestor.
- Next: integrate the tested task branch into dev for coordinator review/replay, then T032 tool-server/session wiring. Disposable daemon/images retained for coordinator replay; no main promotion from this worker. Blockers: none.

### 2026-10-04: T031 physical-validation correction IN REVIEW
- Shared-host physical evidence is rejected. The owned daemon, slirp and containerd exited and no worker container/test remained; worker and independent reviewer both retracted host-containment claims. Elevated key quotas, the loaded docker-default AppArmor profile and an empty `/docker` cgroup remain, but no pre-start baseline exists. Unknown global state was deliberately left unchanged. No absence-of-mutation claim is made.
- An independent prior run of T031's exact verifier on GitHub-hosted Ubuntu in PR #1 job `111408889611` passed `28` sandbox tests in `179.66s`, then `9` acceptance tests in `34.40s`; AC1–AC4 passed. This proves an ephemeral GitHub-hosted runner is a viable physical-validation boundary for that old source, not that the newly found resume/contract issues are resolved.
- Added a pull-request-to-`dev` validation workflow for every project change (image packaging and verifier setup have repository-wide inputs). It has a read-only token, no secrets/OIDC/env, no persisted checkout credential or self-hosted fallback, and uses immutable action SHAs observed in the successful hosted run. One bounded job validates the exact PR head SHA and a second validates GitHub's synthetic merge commit; both run the unchanged T031 verifier. GitHub documentation used: https://docs.github.com/en/actions/using-workflows/events-that-trigger-workflows and https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication.
- Two new static safety tests were written first and failed because the workflow did not exist. They now pass; `make check` exits 0 with `282 passed, 11 deselected`; pre-commit lint/format/types pass. This is not fresh physical evidence. Physical acceptance requires the hosted job on the exact source-repair SHA; resume-readiness and owner-contract repairs remain under independent review.
- No task flag changed, shared-host Docker command ran, production/private-evaluation/model credential was used, or dev/main integration occurred. Owner review/`protected-change` remains required before this protected workflow reaches main.

### 2026-10-04: T031 source/contract review repairs IN REVIEW
- Incorporated the separate worker's resume-readiness ordering, explicit protected-resource absence checks, and actual content-addressed snapshot reads. The proxy must be ready before a stopped analyst starts; readiness failure does not start it. Artifact reads validate ownership, bounded regular no-follow access and SHA-256 integrity.
- Independent review of `d71c074` remained NOT PASS: compressed TAR metadata could conceal the synthetic credential canary; path aliases could defeat destination uniqueness; the snapshot-reader requirement was undeclared in the production interface. All three are repaired here without changing the production `SandboxProvider` protocol or removing existing assertions. Published a separate trusted `SnapshotReader` plus `SnapshotContractAdapter` and documented owner CLI/programmatic integration.
- New regressions reproduced three compressed metadata leaks and three destination aliases as `DID NOT RAISE`, plus an aggregate decompressed-size overflow. The artifact checker now bounds the entire decoded TAR before parsing, scans metadata and payload together, requires canonical destinations, and rejects concatenated/truncated compression. Safe TAR/GZIP/BZIP2/XZ archives still pass. XZ decoder memory is also bounded. This checks artifact bytes; it does not restore archives or detect arbitrary encoded secrets.
- Python 3.12 APIs verified against https://docs.python.org/3.12/library/zlib.html#zlib.Decompress.decompress, https://docs.python.org/3.12/library/bz2.html#bz2.BZ2Decompressor, https://docs.python.org/3.12/library/lzma.html#lzma.LZMADecompressor and https://docs.python.org/3.12/library/tarfile.html. Bounded decoder output and `eof`/`unused_data` checks prevent hidden trailing compression streams.
- Local shared-host-safe checks exit 0: `42 passed, 7 deselected` in sandbox unit tests; `make check` reports `301 passed, 11 deselected, 2 warnings`; Ruff lint/format and strict mypy pass; all pre-commit hooks pass. The owner contract CLI advertises the separate reader factory. No physical Docker command, model call, private-eval access, feature flag change or dev/main integration occurred in this correction.
- Next: independent review of this exact repair and fresh hosted head/merge physical replay. Prior hosted results are not evidence for this repaired revision. T014 remains separately blocked on owner approval for erroneous NOI/reserves assertions; T021 is still an unintegrated review branch.
- Follow-up independent review of `2f75242` correctly remained NOT PASS: concatenated TAR archives could hide a credential filename after the first TAR terminator, even inside a single valid gzip stream. Two new regressions reproduced `DID NOT RAISE`; the checker now requires the remaining end block and entirely zero trailing padding after the parser stops. Both concatenation cases and truncated/nonzero padding regressions pass; valid minimally terminated TAR and all four supported formats still pass. This is an owner-contract false-certification repair, not evidence of a leak in LocalDockerProvider's generated artifacts.
- Final focused local replay: `45 passed, 7 integration deselected`, Ruff lint/format, strict mypy and pre-commit pass. Last full local `make check` on `2f75242` passed 301 tests; the trailing-data correction receives a fresh full hosted replay rather than attributing those older totals to it. Source review and physical replay remain pending on this new revision.
- The next review correctly rejected `d3f98fb`: Python's TAR iterator can swallow an invalid-checksum header, so its consumed block cannot be assumed zero. Raw/single-gzip malformed-header regressions were red first. Termination is now anchored to the last validated member's `offset_data` plus its block-rounded size, with both zero end blocks and all trailing padding checked. Sparse encodings are explicitly rejected so logical and physical file sizes cannot diverge. Safe formats, PAX metadata and a minimally terminated regular TAR remain supported. Verified CPython 3.12.3 `_proc_builtin`/`issparse` against the actual project runtime and official source https://github.com/python/cpython/blob/v3.12.3/Lib/tarfile.py.
- Final focused replay after this correction: `48 passed, 7 integration deselected`; Ruff lint/format, strict mypy and pre-commit passed. New source review and fresh hosted head/merge physical verification remain required. Separately, coordinator replay of T021's exact `70d540c` passed 93 rules tests, AC1/AC2/AC3, `make check` (373 tests), pre-commit and all seven tables from an isolated installed wheel; a second independent read-only review is in progress and its feature flag remains false.
- Independent source review of `049025d` is PASS: the reviewer reports 44 valid and 53 invalid in-memory cases, including every prior reproduction, with no remaining findings. Hosted physical verification remains distinct from that source review. T021's independent `70d540c` review also returned PASS, including 854 classification/replay cases and installed-wheel portability.
- Corrected a stale inherited T031 `passes: true` flag from `f312579` on dev. That flag survived the coordinator's rejection of the shared-host rootful evidence; leaving it true was wrong. It is now false on this repair branch until the exact hosted verifier and source-review conditions are satisfied. No other task flag is changed; the main owner-review/label gates remain intact.

## 2026-10-04 — T031 corrected-source hosted acceptance
- Current-session hosted verifier exited 0 on exact head `d09bb7ab0a53750b2dc5119678ee305d9ea5383c` and synthetic merge `eaadc857d6744dfedfef0d2e2bf52eb9cc2b4fbb` (combined with dev `11705ea`). Checkout and recorded merge SHA were confirmed in full job logs. Each ephemeral runner passed 55 sandbox tests and then the unchanged task checker: `30 passed, 288 deselected`; `T031: AC1 PASSED, AC2 PASSED, AC3 PASSED, AC4 PASSED`. Evidence: PR #3 https://github.com/kavins06/CRE-AI-Agent/pull/3; head job `111417167439`, merge job `111417167550`. Hosted full `make check` job `111417099867` passed 307 tests, 11 integration tests deselected, Ruff/format and strict mypy; dependency audit and test count also passed. The main-only verify-features job was correctly not applicable to this dev PR, not substituted for the exact T031 checker.
- Independent source PASS at `049025d` and exact metadata-only delta confirmation at `d09bb7a` remain applicable. Only after this corrected-source physical evidence was confirmed is T031 completion reasserted. This does not revive the rejected shared-host containment evidence or certify arbitrary runtime/model safety. No private-eval/model credentials or host Docker runtime were used. Owner review/label gates still apply to main promotion.
- This task-metadata/evidence commit changes no source/tests/workflows or verifier; it receives a final head/merge hosted replay before dev integration. T014 remains blocked; reviewed T021 and independent T034 pre-parsing implementation are next.
### 2026-10-04: T034 deterministic document pre-parsing (source-only review)
- Added immutable, strict and bounded parsed-document, table, cell, page and text
  boundaries. Every observation carries the existing canonical `Provenance`, exact
  lexical source text, deterministic IDs, tenant scope, source SHA-256, parser versions
  and a configuration SHA-256. Output round-trips through its schema and is atomically
  confined to `parsed/<doc_id>.json`; it does not create `Fact`, `CalcResult` or canonical
  finance state.
- CSV and XLSX are parsed natively. CSV preserves BOM-sensitive text, quoting, embedded
  newlines, empty cells, leading zeros and explicit delimiters. The OOXML reader retains
  lexical numeric/formula values without float conversion or calculation, validates the
  package with openpyxl, excludes phonetic annotations from rich cell text, and rejects
  macros, external relationships, DTD/entities, unsafe ZIP members and unsupported formula
  forms. File ownership, links, roots, paths, sizes, compression, sheets, rows, columns,
  cells, text and output are bounded; writes use no-follow traversal and atomic replacement.
- Born-digital PDF parsing uses the official Docling 2.133.0 model-free
  `NativePdfPipeline` in a resource-limited subprocess. It blocks network connects, runs
  with offline/model-download variables, retains native text, pages and dimensions, and
  normalizes each Docling box with `to_top_left_origin(page_height)`. There is no OCR,
  layout, table or reading-order inference: scanned/textless pages are explicitly
  `needs_review`. The Reducto seam requires an explicit license and configured typed
  transport; unavailable states raise `ParserUnavailable`, native spreadsheets never reach
  that transport, and there is no successful empty fallback.
- Portable bootstrap decision: regular dependencies now include
  `docling-slim[convert-core,format-pdf]==2.133.0` and `pypdf==6.19.0`; dev adds
  `reportlab==4.4.4` for real synthetic PDFs. The lock changed only root dependency
  metadata. A clean source export ran the unchanged default `init.sh` offline, without
  optional extras, then proved the final parser from its own new venv. It contained
  docling-slim but no full Docling, Torch or NVIDIA distributions; network calls were
  blocked and no models or weights were present or downloaded.
- Tests were written first. Initial collection was RED with
  `ImportError: cannot import name 'Limits'`; later review regressions were also RED for
  phonetic metadata polluting source text and licensed PDF transport seeing CSV/XLSX.
  Neither existing assertions nor acceptance criteria were edited. Final exact verifier:
  ```text
  uv run pytest tests/extraction -q -k preparse && uv run python scripts/check_task.py T034
  .............................................................s           [100%]
  61 passed, 1 skipped in 15.68s
  .............................................................            [100%]
  61 passed, 292 deselected, 2 warnings in 15.86s
  T034: AC1 PASSED, AC2 PASSED, AC3 PASSED
  ```
  The sole skip is the approved `requires_license("REDUCTO")` external call; all mandatory
  native AC tests passed non-skipped. The final isolated clean-install replay produced the
  same 61 passes and all three AC passes.
- Final offline repository check:
  ```text
  make check
  All checks passed!
  94 files already formatted
  Success: no issues found in 62 source files
  341 passed, 1 skipped, 11 deselected, 2 warnings in 73.50s
  ```
- `uv run pre-commit run --all-files` exited 0: ruff lint, ruff format and strict
  source types all passed (rerun after recording this evidence).
- Scope remains deliberately held: T034 `passes` is still false, no PR or dev/main
  integration is authorized here, and no Docker, private evaluations, live data/models or
  production service was used. T010's `DeliverableKind`/NOI acceptance dependency remains
  unresolved; this entry reports isolated T034 source readiness only.
