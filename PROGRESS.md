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
