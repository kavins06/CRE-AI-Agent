# T013: Finance: rent roll and T-12

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M1: Domain and finance core |
| Depends on | T010 |
| Read first | SPEC §6 |
| Allowed to modify | `src/cre_brain/finance/rentroll.py`, `src/cre_brain/finance/t12.py`, `tests/finance/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Deterministic rent roll and T-12 normalization.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t013_ac<n>_*`.
- [ ] AC1 (`test_t013_ac1_*`): rentroll: physical/economic occupancy, GPR, loss-to-lease, concessions, unit mix; returns CalcResult with input ids
- [ ] AC2 (`test_t013_ac2_*`): t12: chart-of-accounts mapping, annualization rules, missing-month policy (flag + impute strategy), one-time item flags
- [ ] AC3 (`test_t013_ac3_*`): Property tests: totals equal sum of parts; occupancy in [0,1]; annualizing 12 months is identity
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/finance -q -k 'rentroll or t12' && uv run python scripts/check_task.py T013
```

## Done when
All ACs are met, verify exits 0, `passes` for T013 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
