# T013: Finance library II: debt, returns, scenarios

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M1: Domain core (branch `milestone/M1`) |
| Depends on | T012 |
| Read first | SPEC §6 |
| Allowed to modify | `src/cre_brain/finance/**`, `tests/finance/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Debt sizing, returns with explicit multi-IRR handling, and joint downside scenarios.

## Acceptance criteria
- [ ] AC1: `debt.py`: sizing as min(LTV, DSCR, debt yield); amortization schedule; IO periods
- [ ] AC2: `returns.py`: IRR/XIRR via pyxirr with multi-root detection (returns status `ambiguous` + roots); equity multiple; cash-on-cash; Excel-convention NPV
- [ ] AC3: `scenarios.py`: sensitivity grid, joint downside (correlated rent/vacancy/exit-cap shocks), `fragility(decision_fn, ranges)`, max-supportable-price solver
- [ ] AC4: Property tests: the amortization balance reaches 0; NPV at the IRR is approximately 0; DSCR decreases as the loan grows; sources equal uses
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/finance -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T013 is set to true, the task branch is merged into `milestone/M1`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
