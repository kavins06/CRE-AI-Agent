# T018: Finance: scenarios, fragility, max price

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M1: Domain and finance core |
| Depends on | T017 |
| Read first | SPEC §6, §11 |
| Allowed to modify | `src/cre_brain/finance/scenarios.py`, `tests/finance/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Decision-robustness tools.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t018_ac<n>_*`.
- [ ] AC1 (`test_t018_ac1_*`): Sensitivity grids; joint downside with correlated shocks within P10–P90 ranges
- [ ] AC2 (`test_t018_ac2_*`): Fragility returns margin-to-flip; CONDITIONAL only if flip within ranges AND margin < fragility_margin
- [ ] AC3 (`test_t018_ac3_*`): Max-supportable-price solver hits a target return within tolerance
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/finance -q -k scenarios && uv run python scripts/check_task.py T018
```

## Done when
All ACs are met, verify exits 0, `passes` for T018 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
