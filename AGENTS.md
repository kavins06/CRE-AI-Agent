# AGENTS.md: instructions for the coding agent (Devin) building this repo

> **What you are building:** an autonomous commercial real estate acquisition analyst, "the Devin of real estate". You (Devin) are the coding agent that builds it. The product contains no coding-agent functionality.

**Read first, in this order:** this file → [METHOD.md](METHOD.md) → [docs/SPEC.md](docs/SPEC.md) → your task file in [docs/tasks/](docs/tasks/). Library usage: [docs/LIBRARY_NOTES.md](docs/LIBRARY_NOTES.md). Do not invent architecture; the decisions are made. If something is truly unspecified, choose the simplest option consistent with SPEC and record it in `PROGRESS.md` under "Decisions".

## Owner-authorized implementation flexibility (2026-10-04)

The owner approved the following in the coordinator conversation:
https://app.devin.ai/sessions/70d6ca47bdbf4faf8083ca76c4988784

- Implementation/build edits may cross task scopes, including **new** CI workflows and portable `.gitignore` rules.
- Coupled tasks may be grouped and reordered to satisfy their actual dependencies.
- Registry-validated dependency/setup corrections and internal architecture improvements are permitted while preserving public interfaces.
- Contradictory process/plumbing may be corrected; acceptance criteria, tests, evaluation bars and security gates must not be weakened.
- Evidence-supported analyst improvements are permitted. Routine implementation choices are autonomous; record decisions in `PROGRESS.md`.

These permissions do **not** authorize changes to existing owner guards (`scripts/check_protected.py`, `scripts/protected_paths.txt`, `.github/workflows/guards.yml`, `CODEOWNERS`), protected-change/owner review bypass, private-eval access, fabricated evidence, or weaker finance/provenance/tenant isolation.
The latest scope excludes SEC downloads/data work; licensed books/articles/reference-library work replaces that sourcing direction.

## Standing owner authorization for main promotion (2026-10-04)

The owner explicitly instructed: “I give you the necessary approval to push to main branch whenever you see fit. Remember this approval for you forever.”
Source: owner instruction in the coordinator conversation, https://app.devin.ai/sessions/70d6ca47bdbf4faf8083ca76c4988784 (owner `user-7ce5aad4a9af47a3a9b9762fcbe17507`).

This standing authorization applies to current and future sessions and supersedes the former blanket ban on agent main promotion. Keep the dev/task-branch/PR workflow: promote tested changes through the milestone PR when appropriate. It does **not** waive required CI, security/evaluation requirements, CODEOWNERS review, the owner's `protected-change` label, immutable owner guards, or the prohibition on force-push/history rewriting. Coordinate promotion with the milestone coordinator; parallel workers must not independently promote the same work.

## Branch model (read carefully)
- **`dev` is the integration branch.** All task state lives there. Never work from `main`.
- Each task goes on a branch `task/<task-id>-<slug>` from `dev`. When verify passes, merge it into `dev` yourself (fast-forward or merge commit). Then push `dev`.
- When every task of a milestone passes on `dev`, open **one PR `dev` → `main`** titled `M<n>: <name>`. Agent main promotion is authorized as above once all applicable gates are satisfied. Keep working on the next milestone on `dev` while the PR waits; you never need `main` to be up to date.

## Session protocol (every session)
1. `git fetch origin && git checkout dev && git pull`. Read `PROGRESS.md` (the last 3 entries) and `feature_list.json` **on `dev`**.
2. Run `./init.sh`, then `make check`. If `dev` is red, fixing it is your task for this session.
3. Pick **the first task in `feature_list.json` with `passes: false` whose `depends_on` all pass**. Work on one task per session.
4. Create the branch `task/<id>-<slug>` from `dev`. Write the tests first. **Every acceptance criterion `ACn` needs at least one test named `test_<id>_ac<n>_*`** (for example `test_t012_ac3_occupancy_bounds`).
5. Run the task's `verify` command. It must exit 0. From T002 onward, its last step is always `uv run python scripts/check_task.py <id>`, which checks that every AC has a passing, non-skipped test.
6. Set only that task's `passes` to `true`. Merge the branch into `dev` and push.
7. Append a `PROGRESS.md` entry: date, task, what changed, the verify tail (30 lines), next step, blockers.
8. If the milestone is now complete, open the `dev` → `main` PR using the PR template.

If you are blocked (a missing secret, an unclear spec, an external outage):
- write a `BLOCKED` entry with evidence and what you need under "Needs owner"
- move on to the next unblocked task
- never fake progress

## Commands
| Purpose | Command |
|---|---|
| Setup (idempotent) | `./init.sh` |
| Lint + types + unit tests + task checks (fast; does **not** run verify_features) | `make check` |
| Unit tests for an area | `uv run pytest tests/<area> -q` |
| Task completeness check | `uv run python scripts/check_task.py <task-id>` |
| Run an eval suite (live, with the Codex CLI) | `make eval SUITE=<name>` |
| Run the analyst on a deal locally | `uv run cre run --deal <path> --request "<text>"` |
| CLI help | `uv run cre --help` |

## Protected paths
- The canonical list is **`scripts/protected_paths.txt`**, written by the owner.
- A PR to `main` that touches any of those paths fails CI unless the owner adds the label `protected-change`. CODEOWNERS also requires the owner's review.
- Task "Allowed to modify" lists are default scopes; the owner authorization above permits required implementation/build edits across those scopes. Protected implementation changes still require the owner's label and review on the milestone PR; owner-authored guards remain immutable.
- **Never** edit `scripts/protected_paths.txt`, `scripts/check_protected.py`, `.github/workflows/guards.yml` or `CODEOWNERS`. New CI workflows are allowed under the owner authorization above; all applicable owner review and protection gates remain.

## Forbidden actions
- **Never** edit, delete, skip or weaken an existing test to make something pass. Skips are allowed only through the approved markers in `tests/conftest.py`: `requires_codex`, `requires_network`, `requires_key(<NAME>)`, `requires_license(<NAME>)`.
- **Never** change a task's `passes` unless its verify command exited 0 in that same session.
- **Never** act as the analyst yourself, read eval truth files, or access the private eval repo. Analyst work runs only through `CodexRunner` in a repo-less container. Scoring is a separate process.
- **Never** hand-write or edit runner transcripts. Transcripts come only from `cre record`. FakeRunner transcripts prove plumbing only; they are **never** evidence of quality.
- **Never** hard-code model names, API keys, emails or personal data. Config and environment variables only.
- **Never** call live models (including the Codex CLI) in unit tests or CI. Live Codex sessions are allowed only in `make eval`, `cre record`, `cre run`, and the learning loop.
- **Never** use `--dangerously-bypass-approvals-and-sandbox` or `danger-full-access` outside a disposable container.
- **Never** add these dependencies: LiteLLM, DSPy (it pulls in LiteLLM), HyperFormula (unless the owner licenses it), Marker, any of ii-agent's office skills, or OpenHands packages.
- **Never** let an LLM produce a number in a deliverable. Every number must resolve to a stored `CalcResult` or `Fact`; the gates check this.
- **Never** force-push `dev` or `main`, or rewrite their history. Main promotion follows the standing authorization and all applicable gates above.

## Environment
- **Analyst runtime (v1):** the **Codex CLI**, pre-installed and authenticated on the build machine. Check it with `codex login status`. For anything touching customer data, the owner uses API-key auth (`CODEX_API_KEY`); see HUMAN_SETUP.
- **Optional:** `TYPESAFE_API_KEY` (Jev, M8). Later: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` (SDK runners, M8).
- **Public data:** `SEC_USER_AGENT` (required for EDGAR), `FRED_API_KEY`, `CENSUS_API_KEY`, `HUD_API_TOKEN`, `BLS_API_KEY`, `SOCRATA_APP_TOKEN`.
- **Infrastructure:** `DATABASE_URL` (Postgres via `docker compose up db` for integration tests; SQLite for unit tests only).
- **CI only (owner-set):** `EVALS_PRIVATE_TOKEN`, for access to the private eval repo.

When a runner or key is unavailable, live work is skipped through the approved markers with `SKIPPED_NO_RUNNER` or `SKIPPED_NO_KEY`. It never crashes.

## Code standards
- Python 3.12, uv, ruff, mypy strict on `src/`, pytest + hypothesis.
- Pydantic v2 at every boundary. `Decimal` for money.
- Tools return concise JSON with actionable error messages.
- One responsibility per module.
- Tests go in `tests/<area>/`. Contract tests for gates, policy, the keep rule and sanitization go in `tests/protected/`.

## Where things are
| Topic | Doc |
|---|---|
| Method and decisions | `METHOD.md` |
| Interfaces, layout, schemas, gates, runner, security | `docs/SPEC.md` |
| Learning loop | `docs/LEARNING.md` + `program.md` |
| Evals | `docs/EVALS.md` |
| Data endpoints and terms | `docs/DATA_SOURCES.md` |
| Owner setup | `docs/HUMAN_SETUP.md` |
| Your reusable procedures | `.agents/skills/*/SKILL.md` |
