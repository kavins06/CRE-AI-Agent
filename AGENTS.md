# AGENTS.md: instructions for the coding agent (Devin) building this repo

> **What you are building:** an autonomous commercial real estate acquisition analyst, "the Devin of real estate". You (Devin) are the coding agent that builds it. The product contains no coding-agent functionality.

**Read first, in this order:** this file → [METHOD.md](METHOD.md) → [docs/SPEC.md](docs/SPEC.md) → your task file in [docs/tasks/](docs/tasks/). Library usage: [docs/LIBRARY_NOTES.md](docs/LIBRARY_NOTES.md). Do not invent architecture: the decisions are already made. If something is truly unspecified, choose the simplest option consistent with SPEC and record it in `PROGRESS.md` under "Decisions".

## Session protocol (every session)
1. `pwd`, then `git fetch origin`. Read `PROGRESS.md` (the last 3 entries) and `feature_list.json`.
2. Run `./init.sh`, then `make check`. If `main` is red, fixing it is your task for this session.
3. Pick **the first task in `feature_list.json` with `passes: false` whose `depends_on` tasks all pass**. Work on one task per session.
4. Branch: `m<milestone>/<task-id>-<slug>`, created from the current milestone branch `milestone/M<n>`. If the milestone branch doesn't exist, create it from `main`.
5. Implement the task. Meet **every** acceptance criterion. Write the tests first where practical.
6. Run the task's `verify` command. It must exit 0. Paste its last 30 lines into `PROGRESS.md`.
7. Change **only** that task's `passes` to `true` in `feature_list.json`. Merge your task branch into `milestone/M<n>`.
8. When every task in the milestone passes, open **one PR**: `milestone/M<n>` → `main`, titled `M<n>: <milestone name>`, using the PR template. Never merge it yourself.
9. Append a `PROGRESS.md` entry: date, task, what changed, verify tail, next step, blockers.

If you are blocked (a missing secret, an unclear spec, an external outage):
- write a `BLOCKED` entry with evidence and what you need under "Needs owner"
- move on to the next unblocked task
- never fake progress

## Commands
| Purpose | Command |
|---|---|
| Setup (idempotent) | `./init.sh` (uv sync, pre-commit, local DB) |
| Lint + types + tests + guards | `make check` |
| Unit tests for an area | `uv run pytest tests/<area> -q` |
| Run an eval suite | `make eval SUITE=<name>` |
| CLI | `uv run cre --help` |
| Protected-file hashes | `uv run python scripts/check_protected.py` |
| Verify all passing features | `uv run python scripts/verify_features.py` |

## Forbidden actions
- **Never** edit, delete, skip or weaken an existing test to make something pass. No new `skip`/`xfail` without a `PROGRESS.md` entry explaining why, with owner sign-off.
- **Never** edit protected paths after they are sealed:
  - `evals/**` is sealed when M2 merges
  - `src/cre_brain/gates/**` and `tests/protected/**` are sealed when M3 merges
  - `program.md`, `CODEOWNERS`, `.github/**`, `PROTECTED_HASHES.txt` are always protected

  Changing a sealed path requires a separate PR labelled `protected-change` and owner review.
- **Never** change a task's `passes` without its verify command exiting 0 in that same session.
- **Never** read `evals/holdout/` or try to reconstruct the sealed test set.
- **Never** hard-code model IDs, API keys, emails or personal data. Config and environment variables only.
- **Never** call live models (including the Codex CLI) in unit tests or CI. Use `FakeRunner` and recorded transcripts. Live Codex sessions are allowed only in `make eval`, `cre record`, and the learning loop.
- **Never** act as the analyst yourself during scored evals, and never read eval truth files. Analyst sessions run through `CodexRunner`, and scoring is a separate blind process.
- **Never** use `--dangerously-bypass-approvals-and-sandbox` outside an isolated box.
- **Never** add these dependencies: LiteLLM, HyperFormula, Marker, or any of ii-agent's bundled office skills.
- **Never** let the LLM do arithmetic in product code. All math goes through `cre_brain.finance`.
- **Never** merge to `main`, force-push, or rewrite history on `main`.

## Environment variables (names only; Devin Secrets supply the values)
- **Analyst runtime (v1):** the **Codex CLI**, pre-installed and authenticated on this machine. No model key is needed. Check it with `codex login status`. Optional: `TYPESAFE_API_KEY` (Jev). Later (M6): `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` for the SDK runners.
- **Public data:** `SEC_USER_AGENT` (required for EDGAR), `FRED_API_KEY`, `CENSUS_API_KEY`, `HUD_API_TOKEN`, `BLS_API_KEY`, `SOCRATA_APP_TOKEN`.
- **Infrastructure:** `DBOS_DATABASE_URL` (default `sqlite:///./.local/dbos.sqlite`), `DATABASE_URL` (default SQLite).
- **CI only:** `EVAL_SEALED_SEED`.

When a runner or key is unavailable, the code must skip live work and log `SKIPPED_NO_RUNNER` / `SKIPPED_NO_KEY`. It must never crash.

## Code standards
- Python 3.12, uv, ruff (format + lint), mypy strict on `src/`, pytest + hypothesis.
- Pydantic v2 models at every boundary. `Decimal` for money.
- Every public function has a docstring and type hints.
- Tool functions return concise JSON with actionable error messages.
- Keep modules small. One responsibility per file.
- Tests live next to the area: `tests/<area>/test_*.py`. Contract tests for gates and evaluators go in `tests/protected/`.

## Where things are
| Topic | Doc |
|---|---|
| Method and decisions | `METHOD.md` |
| Interfaces, layout, schemas, gates, hooks | `docs/SPEC.md` |
| Learning loop | `docs/LEARNING.md` + `program.md` |
| Evals | `docs/EVALS.md` |
| Data endpoints and terms | `docs/DATA_SOURCES.md` |
| Owner setup | `docs/HUMAN_SETUP.md` |
| Reusable procedures for you | `.agents/skills/*/SKILL.md` |
