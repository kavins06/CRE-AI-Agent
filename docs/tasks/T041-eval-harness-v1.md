# T041: Eval harness v1 with blind scoring + first baseline

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M2: First working analyst (thin slice: SCREEN + UW_MODEL via cre run) |
| Depends on | T040, T036 |
| Read first | EVALS §1, §3, §6 |
| Allowed to modify | `evals/harness/**`, `evals/scorers/**`, `reports/**`, `Makefile`, `tests/evals/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
Score the slice honestly.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t041_ac<n>_*`.
- [ ] AC1 (`test_t041_ac1_*`): inspect-ai tasks for SCREEN and UW_MODEL; solver launches the analyst in a repo-less container with only the package
- [ ] AC2 (`test_t041_ac2_*`): Scorer runs after deliverables are copied out; truth read from the separate truth dir; tests prove the analyst container cannot see truth
- [ ] AC3 (`test_t041_ac3_*`): `make eval SUITE=slice_dev` produces reports/evals/<date>.md; when Codex is available, run it and commit the first baseline report
- [ ] AC4 (`test_t041_ac4_*`): CI runs scorer unit tests + FakeRunner plumbing only (no quality claims)
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/evals -q && uv run python scripts/check_task.py T041
```

## Done when
All ACs are met, verify exits 0, `passes` for T041 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
