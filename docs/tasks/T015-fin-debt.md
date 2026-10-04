# T015: Finance: debt sizing, quotes, refinance

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M1: Domain and finance core |
| Depends on | T014 |
| Read first | SPEC §6 |
| Allowed to modify | `src/cre_brain/finance/debt.py`, `tests/finance/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Debt math.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t015_ac<n>_*`.
- [ ] AC1 (`test_t015_ac1_*`): Sizing = min(LTV, DSCR, debt yield); amortization with IO; balance → 0 at maturity (property test)
- [ ] AC2 (`test_t015_ac2_*`): Debt-quote comparison across N term sheets (rate, spread, IO, amort, fees, prepay) → ranked effective cost
- [ ] AC3 (`test_t015_ac3_*`): Refinance at year N given new terms
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/finance -q -k debt && uv run python scripts/check_task.py T015
```

## Done when
All ACs are met, verify exits 0, `passes` for T015 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
