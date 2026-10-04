# T021: Rules engine and default tables

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M1: Domain and finance core |
| Depends on | T010 |
| Read first | SPEC §8 |
| Allowed to modify | `src/cre_brain/rules/**`, `tests/rules/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
zen-engine wrapper + tables.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t021_ac<n>_*`.
- [ ] AC1 (`test_t021_ac1_*`): `rules.evaluate(table, input)` → typed result + trace
- [ ] AC2 (`test_t021_ac2_*`): Tables: buy_box.default, assumption_ranges.mf, loi_policy.default, missing_data_policy, escalation_policy, rent_regulation, tax_reassessment
- [ ] AC3 (`test_t021_ac3_*`): ≥5 example tests per table
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/rules -q && uv run python scripts/check_task.py T021
```

## Done when
All ACs are met, verify exits 0, `passes` for T021 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
