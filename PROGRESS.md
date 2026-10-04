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

### 2026-10-04: T014 pro forma, tax reassessment and value-add
- Added deterministic monthly and annual pro forma calculations for revenue/expense growth, vacancy, post-vacancy credit loss, reserves, property tax, NOI, renovation cost and cash flow. Inputs are frozen Pydantic records, binary floats fail closed, and every calculation runs under the shared isolated 28-digit Decimal context.
- Added jurisdiction-rule tax schedules with explicit assessment ratio, millage, full-reassessment choice, phase-in and annual growth cap. A property-based test proves that a full reassessment after a value increase cannot reduce the current tax; the calculation records whether that conservative floor was applied. Assessment facts and rules have separate provenance IDs.
- Added cohort-based unit-turn schedules with throughput, downtime, cost/unit, current rent, premium and ramp. Monthly offline-unit loss, premium-equivalent units and renovation costs flow into pro forma NOI and cash flow through the source calculation ID; no LLM-generated number or unstored source value enters the projection.
- Red evidence: the new suite initially failed collection because all three finance modules were absent. Exact verification exited 0: `6 passed, 14 deselected`; `T014: AC1 PASSED, AC2 PASSED, AC3 PASSED`. Full `make check` exited 0: Ruff/format clean, strict mypy clean in 53 source files, `265 passed, 4 deselected, 2 warnings in 56.69s`. Only T014's feature flag changed; existing assertions and protected files remain unchanged. No live services, private evaluations, model calls, external data or SEC resources were used. Next: independent review and integration, then T015 debt/returns/waterfall. Blockers: none.
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

- Coordinator assembly on fresh `dev` (`eb19d0b`) retained both additive progress histories. Source review reproduced a current-directory module-shadowing defect in the PDF subprocess: a benign `cre_brain/__init__.py` beside the caller's current directory prevented real parsing. The new regression failed first; the worker now launches Python with `-I -B`, rejecting current-directory/user-site/PYTHON-environment imports and disabling bytecode writes. Official interpreter semantics: https://docs.python.org/3.12/using/cmdline.html#cmdoption-I and https://docs.python.org/3.12/using/cmdline.html#cmdoption-B. Environment budgets/offline SDK flags remain; this is not OS sandbox containment.
- Fresh coordinator verification after the repair: focused regression `1 passed`; extraction verifier `62 passed, 1 skipped` (only approved optional REDUCTO license); task replay `62 passed, 319 deselected`; `T034: AC1 PASSED, AC2 PASSED, AC3 PASSED`; `make check` `369 passed, 1 skipped, 11 integration deselected`; Ruff lint/format, strict mypy and pre-commit all pass. No existing assertions or task flags changed. Independent source review and fresh hosted head/merge checks remain pending. T034 stays false and unmerged because the inherited T010 enum-contract acceptance defect remains owner-held.
- Rights-approved public reference import is now materialized outside Git: 15 government/reference PDFs (1,003 source pages; 2,419 cited chunks), with current artifact/chunk integrity verified. HUD MAP extraction exceeded the unchanged 30-second CPU cap; HUD EMAD returned HTTP 202, so neither is claimed imported. Commercial books remain citation-only unless licensed; no SEC, private eval, tenant facts, credentials or model training entered this cache. This is reference access, not evidence of analyst quality.

## 2026-10-04 — T034 coordinator hardening and verification

- Assembled the reviewed pre-parser on fresh `dev`, retaining the inherited blockers. A red-first
  regression reproduced current-directory Python package shadowing; the PDF worker now uses
  isolated, bytecode-free `python -I -B` startup.
- Final adversarial review reproduced phantom XLSX cells under extension XML. Extraction is now
  confined to direct `sheetData/row/c` elements. Additional red-first hardening preserves hidden
  worksheet visibility warnings, explicitly warns that native PDF text visibility is not verified,
  sanitizes licensed-parser failures, and makes `parsed/<doc>.json` create-only/idempotent so a
  changed source cannot silently replace earlier provenance.
- Fresh exact verification: `66 passed, 1 skipped`; task replay `66 passed, 319 deselected`;
  `T034: AC1 PASSED, AC2 PASSED, AC3 PASSED`. The sole skip is the approved external Reducto
  license test. `make check` passed Ruff, format, strict mypy and `373 passed, 1 skipped,
  11 deselected`; `uv run --locked pre-commit run --all-files` passed all hooks.
- The T034 feature flag remains false and integration remains held because T010 still requires the
  owner-held deliverable-enum contract correction. Existing T010 and T014 assertions were not
  changed.

## 2026-10-04 — T034 final-review follow-up

- Independent review of `2bdcd8a` reproduced a second worksheet-data section being silently
  ignored. The new regression failed before the repair; native XLSX parsing now requires exactly
  one direct `sheetData` section. Two additional red-first cases prove document-derived
  coordinate/shared-string exceptions do not appear in formatted native-parser tracebacks.
- Exact fresh verification: extraction `69 passed, 1 skipped`; task replay `69 passed,
  319 deselected`; `T034: AC1 PASSED, AC2 PASSED, AC3 PASSED`. `make check`: Ruff lint/format,
  strict mypy and `376 passed, 1 skipped, 11 deselected`; all pre-commit hooks passed. The sole
  skip is the approved optional Reducto license seam, not a native parsing gap.
- A built wheel installed into a separate environment parsed a real PDF through the isolated
  worker, preserved the visibility warning and immutable/idempotent output. The successful
  execution was offline with locked dependencies and no Torch/NVIDIA package; no model ran.
- Nonblocking review limitation: concurrent identical writers can fail closed during the short
  two-link publication window; a later retry after cleanup succeeds. No overwrite was observed.
  Same-UID/root hostile mutation and OS containment are not proven by parser file-boundary tests.
- T034 remains false and unmerged pending the T010 enum-contract correction and final review/CI.
  Existing T010/T014 assertions and owner guards remain untouched.

## 2026-10-04 — T034 PR review follow-up

- Automated PR review found three concrete native-format defects. Red-first regressions reproduced
  the standard-library CSV field ceiling despite a larger configured limit, rejection of valid
  explicit `t="normal"` formulas, and irrelevant CSV delimiter configuration changing XLSX
  identities. Native CSV now uses a bounded local strict-dialect parser, ordinary formulas accept
  only the explicit normal type, and parser hashes contain only format-applicable options.
- The fourth review claim was not a defect: both Python's reader and the implementation preserve a
  blank record as a row position, so `A\n\nB\n` anchors `B` at `A3`. A regression now pins this.
- Fresh exact verification: extraction `73 passed, 1 skipped`; task replay `73 passed,
  319 deselected`; `T034: AC1 PASSED, AC2 PASSED, AC3 PASSED`. `make check`: Ruff lint/format,
  strict mypy and `380 passed, 1 skipped, 11 deselected`; all pre-commit hooks passed.
- Acceptance remains held: T034 is false; existing T010/T014 assertions and protected owner guards
  are unchanged.

## 2026-10-04 — T034 streaming budget refinement

- Independent exact-head review of c925817 found no required defects, with 390,624 exhaustive CSV
  dialect comparisons, 4,000 writer round-trips and 17 budget-boundary probes. It identified eager
  row allocation as a nonblocking optimization. Converted the row tokenizer to an iterator so the
  aggregate cell/text budgets can stop consumption before parsing the remaining records.
- A red-first regression proved the former eager implementation scanned a malformed tail instead
  of stopping at the earlier aggregate cell limit. The streaming implementation now fails closed
  at that limit; quote, newline, row-position and field-limit semantics are unchanged.
- Fresh exact verification: extraction `74 passed, 1 skipped`; task replay `74 passed,
  319 deselected`; `T034: AC1 PASSED, AC2 PASSED, AC3 PASSED`. `make check`: Ruff lint/format,
  strict mypy and `381 passed, 1 skipped, 11 deselected`; all pre-commit hooks passed.
- Installed-wheel extraction replay on c925817 passed all 73 tests with the one approved license
  skip. The new streaming head will receive another installed-wheel replay and independent review.
- T034 remains false and integration remains held on T010; no existing assertions or guards changed.
### 2026-10-04: T021 rules — OFFLINE SOURCE-ONLY, ready for independent review
- Branch: `task/T021-rules`, independent checkout from `origin/dev` at `11705ea9055305a093c805b7646dc0439e34d31f`. Initial and final fetch confirmed this base; other workers' remote branches were preserved.
- Changed: strict Pydantic classification/policy/input/trace models, zen-engine 2.1.2 wrapper, seven packaged JDM tables, and 93 non-skipped rules tests. AC3 examples per table: buy-box 10, assumption ranges 9, LOI 9, missing data 7, escalation 8, rent regulation 8, tax reassessment 8. Extra tests exercise typed replay, real ZEN delegation, exact precision/boundaries, configurable policy/profile hashes, path rejection, code-node rejection and no input mutation.
- TDD RED: wrote tests before the adapter/tables; `uv run pytest tests/rules -q` exited **2**, with `ImportError: cannot import name 'engine' from 'cre_brain.rules'`, one collection error. After implementation, 93 rules tests pass; no existing test assertion was changed, removed or skipped.

#### Decisions
- Official references consulted: [Python loader/evaluate guide](https://github.com/gorules/zen/blob/master/bindings/python/README.md), [official JDM table](https://github.com/gorules/zen/blob/master/test-data/table.json), [official trace snapshot](https://github.com/gorules/zen/blob/master/core/engine/tests/snapshots/engine__decision-table-discounts_0.snap), and installed 2.1.2 Python stubs. A real engine probe confirmed `{"trace": True}`, response `result`/`trace`/`performance`, node `traceData` with matching rule `_id`/`index`, and full-expression table predicates before designing the adapter.
- Decimal-only boundary: strict typed Decimal inputs/policy thresholds; cents for amounts, millionths for ratios, integer counts; each transported integer is bounded by `2**53-1`. Scaling uses Decimal tuples and integer division, never float conversion or context-sensitive Decimal arithmetic. Unsupported numeric types, non-finite values, precision and ranges raise validation errors rather than round. Tests include a two-digit Decimal context, millionth boundary differences, cent differences at the maximum exact integer and randomized signed bounded transports.
- Seven allowlisted bundled IDs only. No caller filesystem paths, user-supplied JDM, nested decisions or code nodes. `importlib.resources` loads JSON from the package, not the checkout/CWD. Hatch's existing package selection includes all seven tables, so no build configuration or dependency/lock change was needed.
- Business thresholds are explicit **illustrative configurable firm policy**, not verified market truth: buy-box units 50–500, DSCR minimum 1.25, price maximum 100000000, tiers A/B; LOI DD 15–60 days, closing 30–120 days, deposit maximum 0.03 and financing contingency by default. Assumption profiles explicitly select market tier/class/vintage and configured ranges, with unsupported/overlapping profiles rejected or sent to review. Missing-data critical fields and external-action escalation policy are configurable too.
- No jurisdiction/legal facts are bundled. Rent/tax outcomes require a caller-supplied policy attested verified, nonempty evidence IDs, matching jurisdiction and known status; absent/unverified/mismatched/unknown policy or the `unknown` jurisdiction requires verified policy/evidence. Caller attestation must come from trusted verified evidence in future tool wiring; these classification results neither verify legal truth nor authorize external actions.
- Deterministic immutable trace includes engine/table/policy versions, SHA-256 of source table/policy/input, exact typed input JSON, source and assumption IDs, selected profile, sorted engine nodes and matching rule/index/trace data. Runtime timing is intentionally excluded. Classification is separate from stored Fact/Assumption records and canonical finance CalcResults; no state/database/model calls or T010 DeliverableKind import.

#### Verification evidence
- Exact verifier: `uv run pytest tests/rules -q && uv run python scripts/check_task.py T021` → **exit 0**. Exact output tail:
  ```text
  ........................................................................ [ 77%]
  .....................                                                    [100%]
  93 passed in 0.60s

  ........................................................................ [ 77%]
  .....................                                                    [100%]
  =============================== warnings summary ===============================
  .venv/lib/python3.12/site-packages/typer/__init__.py:24
    /srv/infra/devin-outpost/sessions/devin-92e9e2c3c33b453fb6809c5ffd3a8c9d/workspace/repos/CRE-AI-Agent/.venv/lib/python3.12/site-packages/typer/__init__.py:24: DeprecationWarning: 'click.utils.get_binary_stream' is deprecated and will be removed in Click 9.0.
      from click.utils import get_binary_stream as get_binary_stream

  .venv/lib/python3.12/site-packages/typer/__init__.py:25
    /srv/infra/devin-outpost/sessions/devin-92e9e2c3c33b453fb6809c5ffd3a8c9d/workspace/repos/CRE-AI-Agent/.venv/lib/python3.12/site-packages/typer/__init__.py:25: DeprecationWarning: 'click.utils.get_text_stream' is deprecated and will be removed in Click 9.0.
      from click.utils import get_text_stream as get_text_stream

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  93 passed, 291 deselected, 2 warnings in 1.18s

  T021: AC1 PASSED, AC2 PASSED, AC3 PASSED
  ```
- `make check` → **exit 0**, offline units only (`not integration`), exact output tail:
  ```text
  uv run --locked ruff check src tests
  All checks passed!
  uv run --locked ruff format --check src tests
  88 files already formatted
  uv run --locked mypy src
  Success: no issues found in 56 source files
  uv run --locked pytest tests -m "not integration" -q
  ........................................................................ [ 19%]
  ........................................................................ [ 38%]
  ........................................................................ [ 57%]
  ........................................................................ [ 77%]
  ........................................................................ [ 96%]
  .............                                                            [100%]
  =============================== warnings summary ===============================
  .venv/lib/python3.12/site-packages/typer/__init__.py:24
    /srv/infra/devin-outpost/sessions/devin-92e9e2c3c33b453fb6809c5ffd3a8c9d/workspace/repos/CRE-AI-Agent/.venv/lib/python3.12/site-packages/typer/__init__.py:24: DeprecationWarning: 'click.utils.get_binary_stream' is deprecated and will be removed in Click 9.0.
      from click.utils import get_binary_stream as get_binary_stream

  .venv/lib/python3.12/site-packages/typer/__init__.py:25
    /srv/infra/devin-outpost/sessions/devin-92e9e2c3c33b453fb6809c5ffd3a8c9d/workspace/repos/CRE-AI-Agent/.venv/lib/python3.12/site-packages/typer/__init__.py:25: DeprecationWarning: 'click.utils.get_text_stream' is deprecated and will be removed in Click 9.0.
      from click.utils import get_text_stream as get_text_stream

  -- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
  373 passed, 11 deselected, 2 warnings in 56.20s
  ```
- `uv run pre-commit run --all-files` → **exit 0**:
  ```text
  ruff lint................................................................Passed
  ruff format..............................................................Passed
  strict source types......................................................Passed
  ```
- Wheel: `uv build --wheel` → exit 0, seven JSON resources inspected in `dist/cre_brain-0.1.0-py3-none-any.whl`; installed wheel into project-local `.cache/t021-wheel-venv` and evaluated **all seven** tables with its Python `-I` isolated interpreter. Import path was the wheel environment's `site-packages`, not `src`; resource/hash/deterministic repeat checks all passed. Offline dependency-cache attempt was unavailable; normal project-local pinned dependency install succeeded. No services were involved.

#### Review readiness and dependency acceptance
- Source branch is ready for coordinator **independent review** after exact verifier, offline make check and hooks passed. No milestone/product completion is claimed. T021 flag remains **false**; no feature flag, existing assertion, owner guard, dev/main integration or PR is changed/created.
- **Dependency acceptance BLOCKED/pending (not a local implementation failure):** coordinator reports unresolved T010 uppercase DeliverableKind versus two erroneous lowercase assertions. This wrapper is independent of that enum and does not decide/fix its contract. A passing local offline suite does not resolve that coordinator acceptance issue; T010 acceptance must be settled before integrated T021 acceptance.
- Shared-VPS boundary honored: only source work, project-local uv Python dependencies, public official documentation HTTP, offline unit checks and local wheel verification. No Docker/containerd installation, startup/build, containers, rootful daemon, host permission/sysctl/AppArmor/cgroup changes, shared databases/live services, production/private-eval/SEC data, runtime/integration tests or live model calls.
- Next: push **only** `task/T021-rules` for independent coordinator replay/review. Coordinator retains integration/dependency acceptance; do not merge this branch into dev/main or flip T021 here.

### 2026-10-04: T021 rules — combined-dev assembly verified, acceptance BLOCKED
- Replayed the independently reviewed `70d540c` implementation exactly on a fresh branch from `dev` at accepted T031 commit `eb19d0b`. Rule source, tests, tables, `pyproject.toml` and `uv.lock` are byte-equivalent to the reviewed candidate; the only cherry-pick conflict was additive `PROGRESS.md` history and both histories were retained.
- Exact verifier: `93 passed`; `scripts/check_task.py T021` selected the same 93 tests and reported `AC1 PASSED, AC2 PASSED, AC3 PASSED`. Combined `make check` passed Ruff, format, strict mypy and `400 passed, 11 deselected`; pre-commit passed all hooks.
- `T021.passes` remains **false** and this source branch is not integrated. Required dependency T010 still has the known SPEC mismatch: `DeliverableKind.RENT_COMP_ANALYSIS` and `DEBT_QUOTE_SUMMARY` serialize lowercase while SPEC requires uppercase, and two existing assertions require the incorrect lowercase values. The owner has not yet authorized correction of those assertions. T014's independent NOI/reserve assertion blocker also remains untouched.
- No guard, dependency, acceptance criterion, existing assertion or other task flag changed. Next: owner authorizes the narrow T010 assertion correction; correct and independently verify T010, then replay and accept T021 before `dev` integration.

## 2026-10-04 — T010 owner-approved enum contract correction
- Owner explicitly approved all four previously held enum/NOI corrections in the coordinator conversation. Corrected exactly the two existing DeliverableKind assertions to uppercase and changed all eleven DeliverableKind wire values to the SPEC contract. ClaimType and the event vocabulary are unchanged; no guard, private eval, transcript or protected path changed.
- Red-first replay: 12 deliverable-kind cases failed against lowercase auto() values. After the correction, 32 domain tests pass; added parametrized coverage of all eleven uppercase values, serialized Deliverable JSON and round trips, with lowercase inputs rejected.
- Exact verification exited 0: `uv run --locked pytest tests/domain -q` => `32 passed`; `uv run --locked python scripts/check_task.py T010` => `32 passed, 297 deselected`; `T010: AC1 PASSED, AC2 PASSED, AC3 PASSED`.
- `make check` exited 0: Ruff lint/format and strict mypy pass; `318 passed, 11 deselected`. `uv run --locked pre-commit run --all-files`: all hooks pass. Independent source review and CI remain outstanding; task acceptance/integration remain held until they pass.
### 2026-10-04: T014 independent review; integration BLOCKED
- Fresh adversarial review rejected the initial T014 commit: reserves are incorrectly deducted in NOI, an existing assessed tax basis is ratio-adjusted twice, grown rent is earned by offline units, negative schedule costs can manufacture income, and valid downside assumptions are rejected.
- Fixed the four unblocked source issues with six red-first regression cases: retained assessments now bypass the ratio conversion, full reassessment converts sale price into assessed basis exactly once, value-add exposes separate nominal premium and offline-rent components (offline loss follows base rent growth), schedule costs fail closed, and negative growth greater than -1/full vacancy are accepted. Original test assertions remain unchanged.
- Exact T014 verification freshly exited 0: `12 passed, 14 deselected`; task replay `12 passed, 291 deselected`; AC1–AC3 passed. Full `make check` exited 0: Ruff/format clean in 90 files, strict mypy clean in 57 source files, `292 passed, 11 deselected, 2 warnings in 59.50s`; all pre-commit hooks passed. This does NOT establish correctness of the reserve/NOI convention: the original two NOI assertions encode my error. Accordingly T014's own flag is restored to false after fresh verification and no dev integration is accepted. No model, private evaluation, live service or SEC use.
- Needs owner: explicit permission to correct only the erroneous existing NOI expectations, as requested in the coordinator conversation. Cash-flow expectations and acceptance criteria remain unchanged. The source repair and independent re-review must follow before T014 integration. T015 preparation may continue, but dependency completion is not claimed.

### 2026-10-04: T031 coordinator safety review; NOT ACCEPTED
- Independent reviewer and coordinator observed the retained Docker daemon as host UID/GID 0 with the host user namespace, full effective capabilities and no no-new-privileges/seccomp confinement; only mount/network namespaces differed. Coordinator did not run the proposed physical replay. Rootful daemon authority is not contained by those two namespaces, so the preceding claim that no shared-host state was changed is not independently established. Actual global mutations are not yet proven or excluded.
- The implementation workflow is paused. Worker420 was instructed to stop only its owned disposable processes, preserve evidence, inspect possible host-wide effects read-only, and not restore unknown prior sysctl/AppArmor values. No further rootful Docker or host policy changes are authorized on this shared VPS.
- Source review also found resume missing the firewall/proxy readiness gate, and reusable owner-contract checks that could falsely certify protected-resource absence/snapshot safety. Worker420 is repairing source with offline tests only on a separate task branch; no coordinator acceptance, physical-security completion, or main promotion is claimed.
- The inherited worker T031 flag remains true only because the repository forbids flag changes without successful same-session exact verification; it is NOT a coordinator security acceptance. Do not schedule dependent sandbox tasks or promote based on that flag. Safe independent physical validation requires an already-authorized fully contained runtime or dedicated disposable machine, plus resolved source findings. Runtime cleanup/effects report remains pending.

## 2026-10-04 — T014 approved below-NOI reserves repair IN REVIEW
- Assembled the held T014 source onto current dev plus the T010 enum correction. The only merge conflict was an additive PROGRESS.md tail; both evidence histories were retained, including later T031 acceptance. No sandbox source, workflow or guard changed.
- Corrected exactly the two owner-approved NOI expectations: first month 5550 and month 13 6255. Annual cash-flow expectations remain unchanged. NOI excludes replacement reserves and renovation costs; cash flow deducts both below NOI. Added three reserve scenarios including zero and negative cash flow, real tax/renovation schedules, monthly identities, annual totals and the partial second year.
- Red-first focused replay: `3 failed, 1 passed, 25 deselected`; the two nonzero-reserve cases and original corrected expectation failed against the prior source. After the two-line finance repair, exact verification exited 0: `15 passed, 14 deselected`; checker `15 passed, 329 deselected`; `T014: AC1 PASSED, AC2 PASSED, AC3 PASSED`.
- `make check`: Ruff lint/format and strict mypy pass; `333 passed, 11 deselected`. All pre-commit hooks pass. T014 remains false until fresh independent review and CI. T010 PR review found historical lowercase deliverable-read compatibility, being repaired separately before integration.

### T010 historical deliverable compatibility repair
- PR #6 review correctly found that old lowercase deliverable payloads would no longer validate. Eleven red-first historical-row tests reproduced it. Added an exact allowlisted storage-read adapter only for legacy Deliverable kinds after the tenant-scoped query. New domain inputs remain uppercase-only; new appended payloads serialize uppercase. Existing versioned rows are not migrated or rewritten, preserving immutable audit history.
- Tests cover every legacy kind, historical/current reads, both tenant boundary mismatches, next-version append and byte-equivalent stored JSON values after reads; six invalid/mixed-case/unknown kinds remain rejected. No existing assertion was changed beyond the two owner-approved enum expectations.
- Fresh verification exited 0: domain+store tests `59 passed`; T010 checker `32 passed, 314 deselected` (AC1–AC3); T011 checker `37 passed, 309 deselected` (AC1–AC4). `make check` and all pre-commit hooks pass: `335 passed, 11 deselected`; Ruff lint/format and strict mypy green. Independent source review and hosted CI are still required for this repaired head.

### Verification record corrections and fresh combined T014 replay
- Correction to the preceding T010 store record: actual T011 checker output was `47 passed, 4 skipped, 295 deselected`, AC1–AC3 (there is no AC4 in T011). The four approved integration-key skips are not PostgreSQL evidence. T010 and full-check totals were recorded correctly.
- Correction to the initial T014 full-check record: that run actually failed the fresh-archive test because the resolved PROGRESS.md conflict had not been staged. It reported `1 failed, 332 passed, 11 deselected`; pre-commit had not run from that chained command. No test was skipped or weakened to fix this: stage the resolved index, incorporate the historical-read repair, then rerun.
- Fresh combined T014 exact verify now exits 0: `15 passed, 14 deselected`; checker `15 passed, 346 deselected`; AC1–AC3 passed. Full `make check` exits 0 with `350 passed, 11 deselected`; Ruff lint/format, strict mypy and all pre-commit hooks pass. Independent source review and CI remain pending; T014 stays false.

## 2026-10-04 — T021 combined dependency replay
- T010 source review passed on exact `772c6e4`, including eleven legacy-kind regressions and immutable historical storage. PR #6 hosted CI settled: five passed, zero failed/pending, one main-only verifier not applicable. Owner-approved enum assertion repair is no longer held. The T011 count correction above is authoritative.
- Assembled rules with the corrected T010 and T014 review candidate, retaining all progress histories across an additive log-only conflict. Rules source/tests/tables are unchanged from the independently reviewed candidate.
- Fresh exact T021 verification exited 0: rules `94 passed`; checker `94 passed, 361 deselected`; AC1–AC3 passed. Full `make check`: `444 passed, 11 deselected`; Ruff lint/format, strict mypy and all pre-commit hooks pass. Combined review/CI remain outstanding; T021 stays false until acceptance.

## 2026-10-04 — T034 combined dependency replay
- Assembled the reviewed parser with current domain correction, T014 below-NOI repair and T021 rules candidate, retaining both additive progress histories. Parser source/tests and locked dependencies are unchanged from independently reviewed `91517ca`; real model-free Docling, inert XLSX formulas and bounded/lazy CSV behavior remain intact. No protected source/guards changed.
- Fresh `./init.sh` exited 0 using locked dependencies and installed the existing pre-commit hook. Exact T034 checker exited 0: `74 passed, 456 deselected`; AC1–AC3 passed. Full `make check` exited 0 with `518 passed, 1 approved Reducto-license skip, 11 integration deselected`; Ruff lint/format, strict mypy and all pre-commit hooks pass. No licensed Reducto execution, private eval, SEC, live model or shared-host Docker use is claimed.
- Fresh combined-source review and head/merge hosted CI remain outstanding. T034 stays false until acceptance. Finance independent review separately passed exact `d48f9f7`, including deterministic-context and monthly/annual oracle checks.
## 2026-10-04 — T014 acceptance candidate after corrected finance review
- Independent finance reviewer passed exact `d48f9f7`: all five prior required findings resolved; 29 finance tests, exact 15-test selection/AC1–AC3 and focused lint/types pass. Independent synthetic oracles cover 216 tax cases, 648 projections/13,392 monthly identities and partial-year totals; 69 malformed inputs reject; caller Decimal context remains unchanged. Review found no blocking/nonblocking source issues.
- Fresh same-session task replay on this branch exits 0: `15 passed, 346 deselected`; AC1–AC3 passed. PR #7 actual head/merge hosted checks and dependency audit/test count/local check all pass (five checks); main-only verify-features is not applicable. T014 alone is marked true. Final metadata-head CI and automated PR review remain integration gates; no merge is claimed yet.

## 2026-10-04 — T021 acceptance candidate after combined review
- Independent reviewer passed exact `e3ae713`: rules source/tests byte-identical to `4814220`, 217 focused tests and 78 cross-module assertions, full `make check` (444), and exact T021 checker (94; AC1–AC3) passed. Current source matches that head; latest dependency delta only marks reviewed T014 true and records evidence.
- Fresh same-session rules verification exits 0: `94 passed`; checker `94 passed, 361 deselected`; AC1–AC3 pass. T021 alone marked true. Final head/merge CI remains the integration gate; no dev merge is claimed yet.
- Integration boundaries for T032/adapters: resolve policy source IDs against tenant-owned verified records before applying jurisdiction rules (caller-supplied verification is not authorization). Finance-to-rules adapters must enforce exact cents/millionths with explicit precision treatment; unsupported precision is rejected, never silently rounded. These are documented boundaries, not source-review blockers.

## 2026-10-04 — T034 acceptance candidate after combined review
- Independent parser/cross-module reviewer passed exact `761fcde`, confirming parser and locked dependencies identical to `91517ca`, reviewed finance/rules/domain state contracts, forged-provenance rejection and synthetic SQL/JSON provenance round trips. Clean locked `make check`: `518 passed, 1 approved Reducto skip, 11 integration deselected`; exact T034 replay `74 passed`, AC1–AC3 pass. Initial independent harness Git/venv failures were corrected by a clean isolated worktree, not source/test edits.
- Fresh same-session exact T034 verify on the final metadata assembly exits 0: parser `74 passed, 1 approved Reducto skip`; checker `74 passed, 456 deselected`; AC1–AC3 pass. T034 alone marked true after the above verification and source review. The incoming T014/T021 flags are those tasks' separately verified changes. Source/tests/dependencies remain unchanged; no security gate changes.
- Final head/merge hosted CI remains outstanding before dev integration. Optional Reducto licensed execution and same-UID/root adversarial isolation are not claimed. The reference cache is external to Git; no SEC/private evaluation/model calls were used.

## 2026-10-04 — T015 author candidate (acceptance pending)
- Isolated checkout from origin/dev `5afde310256b5f988d17cef78d02644ddc0fe5fc`; required accepted base is exactly this base. Locked `./init.sh` and baseline `make check` exited 0: 518 passed, one approved optional Reducto-license skip, 11 integration deselected.
- Tests first: the new debt AC suite failed collection with `ModuleNotFoundError: No module named 'cre_brain.finance.debt'` (29 deselected, one error). Added Decimal sizing, monthly IO/amortization, borrower-yield quote ranking and payment-date refinancing. No existing tests/assertions or public domain schemas changed.
- Decisions: the task's shorthand "balance → 0 at maturity" is satisfied by a separately reported balloon payment, never by deleting debt. IO defers the start of amortization; DSCR sizing uses the post-IO constant except for entirely IO terms. Fully IO zero-rate DSCR is explicitly undefined/nonbinding. Base plus spread is a fixed quoted rate, not an invented forward-rate curve.
- Effective quote cost is the annually compounded monthly borrower IRR of net proceeds versus scheduled payments, balloon and early-prepayment fees. Fees are fixed plus percentage of principal; prepayment percentage applies to outstanding balance only before maturity. Exact ties sort by quote input ID. Optional common payoff horizon is a stored input, otherwise each contractual maturity is used.
- Refinance is on contractual monthly anniversaries (day clamped to month end), after the old month's scheduled payment and before its balloon. Maturity refinancing therefore pays the remaining balance. Negative cash-out means equity required, not magically generated proceeds. Every source and optional horizon/NOI has a stored input ID. Outputs use isolated 28-digit half-even Decimal arithmetic without silent money quantization.
- Exact verify exited 0: `uv run pytest tests/finance -q -k debt && uv run python scripts/check_task.py T015`. Tail:
```text
...........                                                              [100%]
11 passed, 29 deselected in 0.50s

...........                                                              [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/typer/__init__.py:24
  DeprecationWarning: 'click.utils.get_binary_stream' is deprecated and will be removed in Click 9.0.
    from click.utils import get_binary_stream as get_binary_stream

.venv/lib/python3.12/site-packages/typer/__init__.py:25
  DeprecationWarning: 'click.utils.get_text_stream' is deprecated and will be removed in Click 9.0.
    from click.utils import get_text_stream as get_text_stream

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
11 passed, 530 deselected, 2 warnings in 1.37s

T015: AC1 PASSED, AC2 PASSED, AC3 PASSED
```
- Full `make check`: Ruff lint/format, strict mypy (68 source files) and 529 tests pass; one approved Reducto-license skip and 11 integration deselections. All pre-commit hooks pass. No runtime/approval blocker; next implement T016, then independent review. T015 remains false; no PR, dev/main merge or acceptance is claimed.

## 2026-10-04 — T016 author candidate (acceptance pending)
- Tests first: the new returns AC suite failed collection with `ModuleNotFoundError: No module named 'cre_brain.finance.returns'` (40 deselected, one error). Added Decimal IRR/XIRR, MIRR fallback, Excel-timed NPV, equity multiple and cash-on-cash. No existing tests/assertions, dependency pins or public domain schemas changed.
- Decision: IRR roots are isolated over the exact open domain `(-0.99, 10)`, not sampled from a grid. With `q=1/(1+r)`, periodic and ACT/365-dated NPV are generalized polynomials. Recursively isolating derivative roots partitions the full domain into monotone intervals, so tangent and close roots are retained. Repeated dates are aggregated, unordered dates are sorted, all-zero NPV is explicitly infinitely ambiguous and same-date nonzero NPV is undefined.
- A unique root is reported as IRR/XIRR. Multiple roots are all listed and status is ambiguous, with dated or periodic MIRR as fallback; no roots are undefined. Root counts above the bounded 128-point nonconventional search or roots unresolved at 28 output digits fail closed. Every reported root is independently residual-checked below relative `1e-24`; a generated one-to-four-root property suite exercises the search.
- Decision: pyxirr 0.10.8 is called as a binary64 cross-check (`irr`/`xirr` and `npv(..., start_from_zero=False)`) after normalizing cash flows. It never defines root count or authoritative output. Decimal arithmetic uses 80+ internal digits for root isolation and isolated 28-digit half-even public results. Binary64 underflow/overflow is flagged unsupported; no pyxirr float becomes authoritative money or a reported root.
- The suite covers two/three roots, tangent and roots separated by `1e-12`, cash-flow scales `1e-200` through `1e200`, exact/near open boundaries, zero and negative rates, irregular and repeated dates, invalid date/count/float/NaN inputs, dated MIRR, Excel examples, caller Decimal context, serialization, contribution-aware equity multiple and negative cash-on-cash.
- Exact verify exited 0: `uv run pytest tests/finance -q -k returns && uv run python scripts/check_task.py T016`. Tail:
```text
...................................                                      [100%]
35 passed, 40 deselected in 0.99s

...................................                                      [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/typer/__init__.py:24
  DeprecationWarning: 'click.utils.get_binary_stream' is deprecated and will be removed in Click 9.0.
    from click.utils import get_binary_stream as get_binary_stream

.venv/lib/python3.12/site-packages/typer/__init__.py:25
  DeprecationWarning: 'click.utils.get_text_stream' is deprecated and will be removed in Click 9.0.
    from click.utils import get_text_stream as get_text_stream

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
35 passed, 541 deselected, 2 warnings in 1.92s

T016: AC1 PASSED, AC2 PASSED, AC3 PASSED
```
- Full `make check`: Ruff lint/format, strict mypy (69 source files) and 564 tests pass; one approved Reducto-license skip and 11 integration deselections. All pre-commit hooks pass. No runtime/approval blocker. T015/T016 remain false pending independent review; no PR, dev/main merge or acceptance is claimed.

## 2026-10-04 — T015 required-review R1 repair (acceptance pending)
- Accepted base verified exactly at origin/dev `5afde310256b5f988d17cef78d02644ddc0fe5fc`; locked bootstrap and baseline `make check` pass: 518 passed, one approved Reducto-license skip, 11 integration deselected. Incoming task branch retained; repair adds commits without rewriting.
- Red-first regressions reproduced wrong payments/balances at annual rates 1e-25 and 1e-26 and DivisionByZero at 1e-27 and 1e-80, including fully IO refinancing: 12 failed, 4 passed, 75 deselected.
- Decision: evaluate the finite annuity as a Horner sum of discounted unit payments, then divide principal by that positive sum. No subtraction of almost-equal powers, rate cutoff or near-zero division; the zero-rate limit is continuous. Interest still uses the actual positive rate, with isolated 28-digit outputs. Twelve-month payments match an independent 150-digit closed-form oracle; DSCR sizing remains approximately 96, never the erroneous 115.2. Balloon/IO/fees/provenance semantics are unchanged.
- Focused Ruff and strict mypy (69 files) pass. Exact T015 verify exits 0; tail:
```text
...........................                                              [100%]
27 passed, 64 deselected in 0.52s

...........................                                              [100%]
27 passed, 565 deselected, 2 warnings in 1.45s

T015: AC1 PASSED, AC2 PASSED, AC3 PASSED
```
- Both acceptance flags remain false. Next: repair T016 R2, then coupled full checks and independent review. No PR or dev/main integration; no blocker.

## 2026-10-04 — T016 required-review R2 repair (acceptance pending)
- Red-first cancellation/permutation regressions reproduced incorrect root counts at 1e80, 1e100 and 1e200, changed close/tangent roots, and absent rejection at unsupported exponent span: 9 failed, 1 passed, 91 deselected.
- Decision: compute working precision from the largest adjusted exponent minus the smallest nonzero coefficient exponent, plus a sum-growth allowance based on input count and 40 guard digits. This bounds exact duplicate-date additions independent of order, including the net +1 from [1e200, 1, -1e200]. Precision remains bounded to 80–256 digits; unsupported spans reject before arithmetic instead of silently dropping a cash flow. Public results remain isolated 28-digit Decimal; pyxirr remains a binary64 diagnostic, never authoritative.
- The expanded working precision exposed a previously insufficient bisection budget (5 failed, 40 passed): its old budget measured the length of scientific-notation text, not requested accuracy. Budget now scales to the actual epsilon exponent, bounded by the existing 256-digit limit. Regression checks retain all roots, including tangent/1e-12-separated cases after large cancellations.
- New tests exercise 96 cash-flow/date permutations, 24 close/tangent cancellation permutations, six fail-closed permutations, hostile caller context and CalcResult JSON round trips. No existing assertions/skips or public schemas changed.
- Focused Ruff and strict mypy (69 files) pass; lock synchronization remains unchanged. Exact T016 verify exits 0; tail:
```text
.............................................                            [100%]
45 passed, 56 deselected in 1.43s

.............................................                            [100%]
45 passed, 557 deselected, 2 warnings in 2.85s

T016: AC1 PASSED, AC2 PASSED, AC3 PASSED
```
- Both flags remain false. Next: coupled full checks/hooks and push for independent review. No PR or dev/main integration; no blocker.

## 2026-10-04 — T015/T016 repair coupled-head replay (acceptance pending)
- Separate source/test repair commits preserve incoming history: T015 `fde540db85cf503280331e80a90e549a71c4d21b`; T016 `6729438cd68e501e280683e626224720a8f141fd`.
- Exact verifiers replayed sequentially on that coupled source head:
```text
27 passed, 74 deselected in 0.52s
27 passed, 575 deselected, 2 warnings in 1.44s
T015: AC1 PASSED, AC2 PASSED, AC3 PASSED
45 passed, 56 deselected in 1.57s
45 passed, 557 deselected, 2 warnings in 2.58s
T016: AC1 PASSED, AC2 PASSED, AC3 PASSED
```
- Full `make check` exits 0:
```text
uv run --locked ruff check src tests
All checks passed!
uv run --locked ruff format --check src tests
108 files already formatted
uv run --locked mypy src
Success: no issues found in 69 source files
uv run --locked pytest tests -m "not integration" -q
590 passed, 1 skipped, 11 deselected, 2 warnings in 89.88s (0:01:29)
```
- The sole skip remains the approved Reducto-license seam; integration is excluded by the documented fast suite. All pre-commit hooks (Ruff lint/format, strict source types) and `uv lock --check` pass. Typer/Click deprecation warnings are unchanged.
- Additional independent 160-digit closed-form payment oracle and contractual final-balance checks pass for 120 combinations spanning principal 1200/1e9, 1–600 months and annual rates 0, 1e-80, 1e-27, 1e-26, 1e-25, 1e-15, .01, .06, .12 and 1. Replaying the ten new T016 regression cases in-memory against incoming `8fff2d4` reconfirms 9 failures and one pass without modifying tracked source.
- Feature flags stay false; no existing tests/assertions, schemas, pins or protected guards changed. Ready for task-branch push and independent review; no PR, dev/main merge, main promotion, live models, private eval, SEC or UI testing. No blocker.

## 2026-10-04 — T016 required-review R3 certified-cardinality repair (acceptance pending)
- Isolated session-local clone; fetched incoming branch without rewriting it. Required accepted base remains exactly origin/dev `5afde310256b5f988d17cef78d02644ddc0fe5fc`. Ran locked `./init.sh` and baseline `make check` on that base: 518 passed, one approved Reducto-license skip, 11 integration deselected; Ruff lint/format and strict mypy (67 files) pass.
- Red first, before source edits: 27 failed, 3 passed in the new AC1/AC3 certification suite. Reproduced the review's two-root collapse at gaps 1e-35, 1e-40 and 1e-100, scaled and dated variants, absence of output-collision rejection, collapsed cubic tangency plus a close root, and false exact-zero reporting for irregular tangencies.
- Decision: aggregate on exact integer periods/days, shift the first nonzero time, then reduce the lattice by its integer GCD. For reduced degree at most 128, convert original Decimal coefficients losslessly to standard-library Fraction and use exact Sturm sign variations to count distinct roots in each bracket. Repeated roots are counted once; a tiny stationary residual never certifies tangency. Exact rational open-domain endpoint factors are removed with all multiplicities; irrational endpoint brackets are padded outward and unresolved boundary conversions reject. Brackets refine by width, not residual, with an exact q=1 split preserving zero roots. Only the final rational-to-Decimal root/rate conversion is rounded; root collisions still reject at 28 output digits.
- Decision: retain bounded generalized-polynomial derivative isolation for larger reduced lattices, but fail closed on uncertified stationary/boundary signs or an exactly rounded bisection value. Do not return an artificial tangent root or silently omit adjacent brackets. Rational remainder intermediates are bounded to 16384 bits; separation depth is bounded by working precision. Unsupported complexity/precision produces actionable ValueError, not fake uniqueness. These bounds and the 80–256-digit conversion / 28-digit public / binary64-diagnostic boundaries are documented in the module.
- New tests cover representable near-zero pairs and unrepresentable nonzero pairs, exact repeated roots with a nearby distinct root, both sides of a nearly tangent stationary point, reduced irregular date tangency, safely rejected uncertified large-lattice tangency, actual 1/182/365/730-day conversion, exact endpoint multiplicities, caller-context preservation and CalcResult JSON. Expanded returns selection: 86 passed (41 new tests plus all 45 existing returns cases). No existing assertion, public schema, lock/pin, finance provenance contract or acceptance flag changed. T015 source is unchanged from the separately committed incoming repair.
- Final exact T015 verify exits 0:
```text
...........................                                              [100%]
27 passed, 115 deselected in 0.63s

...........................                                              [100%]
27 passed, 616 deselected, 2 warnings in 1.53s

T015: AC1 PASSED, AC2 PASSED, AC3 PASSED
```
- Final exact T016 verify exits 0; verify tail:
```text
........................................................................ [ 83%]
..............                                                           [100%]
86 passed, 56 deselected in 5.79s

........................................................................ [ 83%]
..............                                                           [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/typer/__init__.py:24
  DeprecationWarning: 'click.utils.get_binary_stream' is deprecated and will be removed in Click 9.0.
    from click.utils import get_binary_stream as get_binary_stream

.venv/lib/python3.12/site-packages/typer/__init__.py:25
  DeprecationWarning: 'click.utils.get_text_stream' is deprecated and will be removed in Click 9.0.
    from click.utils import get_text_stream as get_text_stream

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
86 passed, 557 deselected, 2 warnings in 6.82s

T016: AC1 PASSED, AC2 PASSED, AC3 PASSED
```
- Full sequential validation exits 0: `make check` reports 631 passed, one approved Reducto-license skip, 11 integration deselected (89.67s); Ruff lint/format (109 files), strict mypy (69 source files), all pre-commit hooks and `uv lock --check` pass. No overlapping pytest commands, new runtime, host service/policy changes, UI, models, SEC or private evaluations.
- Next: additive T016 source/test repair commit and push for fresh independent review. T015/T016 flags remain false. No PR, dev/main merge, promotion or acceptance; no approval/runtime blocker.

## 2026-10-04 — T015/T016 final precision repair (acceptance pending)
- The bounded workflow stopped after three independent review rounds, without accepting defective work. Last review reproduced positive borrowing costs rounded to zero and exact Excel NPV cancellation losing a representable unit; both repaired on a new branch from reviewed `539f50e`, not dev/main.
- Red first: 20 new precision/complexity regressions failed before source edits. No pre-existing assertions, skips, schemas, pins or guards changed. The draft new complexity case incorrectly demanded rejection of an ordinary 600-period nine-digit rate; replaced that unreasonable uncommitted case with genuinely oversized arithmetic and added explicit normal-600-period support. The draft diagnostic assertion also wrongly required binary disagreement for every permutation; strengthened it to an independent Fraction check of whether the actual binary result agrees.
- Decision: derive quote working precision from all positive input exponent spans plus 40 guard digits (80–256 bound); construct schedules, fees, proceeds and root search at that precision, scale the bisection budget accordingly, and round public outputs once to isolated 28 digits. Unsupported spans reject before calculation; a positive cost is never deliberately treated as free.
- Decision: Excel-timed NPV uses exact Fraction Horner arithmetic, with one final 28-digit Decimal rounding. Bound initial operands to 4096 decimal digits and rational intermediates to 65536 bits; unsupported complexity fails closed. Binary64 pyxirr remains advisory and reports consistency only relative to the actual nonzero NPV, not the much larger gross-flow scale; conversion underflow is unsupported.
- New coverage: tiny rates/fees down to 1e-180, principal scaling, quote ordering, 18 exact cancellation permutations, nonzero-discount cancellation, caller context/signals, CalcResult serialization, genuine complexity limits and a conventional 600-period model.
- Exact/focused replay exits zero:
```text
134 passed, 29 deselected
48 passed, 616 deselected
T015: AC1 PASSED, AC2 PASSED, AC3 PASSED
97 passed, 567 deselected
T016: AC1 PASSED, AC2 PASSED, AC3 PASSED
```
- Full `make check`: 652 passed, one approved Reducto-license skip, 11 integration deselected; Ruff lint/format, strict mypy (69 source files), all pre-commit hooks and locked dependency check pass. No overlapping test processes.
- Coordinator also replayed the accepted dev verifiers: all numerical/domain/state/parser checks passed. The interrupted duplicate replay caused a checkout-local pytest basetemp race in T002; serialized T002 replay is green. T031 physical verification is unavailable locally because Docker is deliberately absent; accepted hosted head/merge validation remains the physical evidence, not a claim of full local verify_features success.
- Next: push repaired head for fresh independent review. Both task flags remain false; no PR, dev/main integration, live models, SEC, private eval or shared-host runtime changes.
