# T058: Private holdout scoring service

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M3: Evals on real anchors |
| Depends on | T041 |
| Read first | EVALS §1, §4 |
| Allowed to modify | `evals/service/**`, `.github/workflows/score.yml`, `tests/evals/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
Holdout confirmation without exposing cases. Note: .github is protected; this PR needs the owner label.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t058_ac<n>_*`.
- [ ] AC1 (`test_t058_ac1_*`): CI workflow `score.yml` (workflow_dispatch) checks out the private repo with EVALS_PRIVATE_TOKEN, runs scoring for a release id, returns only pass/fail + aggregates as an artifact
- [ ] AC2 (`test_t058_ac2_*`): `cre evals confirm --release R --kind K` triggers it and polls; never downloads cases
- [ ] AC3 (`test_t058_ac3_*`): Without the token, skips with requires_key(EVALS_PRIVATE_TOKEN)
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/evals -q -k service && uv run python scripts/check_task.py T058
```

## Done when
All ACs are met, verify exits 0, `passes` for T058 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
