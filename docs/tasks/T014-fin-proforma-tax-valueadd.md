# T014: Finance: pro forma, tax reassessment, value-add

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M1: Domain and finance core |
| Depends on | T013 |
| Read first | SPEC §6 |
| Allowed to modify | `src/cre_brain/finance/proforma.py`, `src/cre_brain/finance/taxes.py`, `src/cre_brain/finance/valueadd.py`, `tests/finance/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Operating projections incl. reassessment and renovation schedules.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t014_ac<n>_*`.
- [ ] AC1 (`test_t014_ac1_*`): proforma: monthly/annual with growth, vacancy, credit loss, reserves
- [ ] AC2 (`test_t014_ac2_*`): taxes: reassessment on sale from a jurisdiction rule input (ratio, millage, phase-in, caps); property test: reassessed ≥ current when price > assessed (full-reassessment jurisdictions)
- [ ] AC3 (`test_t014_ac3_*`): valueadd: units/month turn schedule, downtime, cost/unit, premium, ramp; NOI impact feeds proforma
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/finance -q -k 'proforma or taxes or valueadd' && uv run python scripts/check_task.py T014
```

## Done when
All ACs are met, verify exits 0, `passes` for T014 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
