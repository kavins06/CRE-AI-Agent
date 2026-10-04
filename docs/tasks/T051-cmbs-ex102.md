# T051: CMBS EX-102 multifamily loans

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M3: Evals on real anchors |
| Depends on | T050 |
| Read first | EVALS §2 C |
| Allowed to modify | `evals/cmbs/**`, `src/cre_brain/data/**`, `tests/evals/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
Parse EX-102 and build multifamily loan histories.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t051_ac<n>_*`.
- [ ] AC1 (`test_t051_ac1_*`): Discover CMBS ABS-EE filings; parse EX-102; filter propertyTypeCode MF
- [ ] AC2 (`test_t051_ac2_*`): Per loan: securitization fields (NOI, NCF, occupancy, DSCR, value, units) + monthly outcome series
- [ ] AC3 (`test_t051_ac3_*`): ≥5 offline fixtures; `cre evals build-cmbs --limit N` (target ≥100) when network available
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/evals -q -k ex102 && uv run python scripts/check_task.py T051
```

## Done when
All ACs are met, verify exits 0, `passes` for T051 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
