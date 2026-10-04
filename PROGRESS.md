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
