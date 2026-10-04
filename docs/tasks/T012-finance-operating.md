# T012: Finance library I: operating cash flow

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M1: Domain core (branch `milestone/M1`) |
| Depends on | T010 |
| Read first | SPEC §6 |
| Allowed to modify | `src/cre_brain/finance/**`, `tests/finance/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Deterministic rent roll, T-12 and pro forma functions returning CalcResult.

## Acceptance criteria
- [ ] AC1: `rentroll.py`: occupancy (physical and economic), GPR, loss-to-lease, concessions, unit-mix summary
- [ ] AC2: `t12.py`: line mapping to a standard multifamily chart of accounts, annualization rules, missing-month policy (flag + impute strategy param)
- [ ] AC3: `proforma.py`: annual and monthly cash flows with growth, vacancy, credit loss, reserves and capex
- [ ] AC4: Every public function returns `CalcResult` with input IDs
- [ ] AC5: Property tests: totals equal the sum of parts; occupancy is in [0,1]; annualizing 12 months is the identity
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/finance -q -k 'rentroll or t12 or proforma'
```

## Done when
All ACs are met, verify exits 0, `passes` for T012 is set to true, the task branch is merged into `milestone/M1`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
