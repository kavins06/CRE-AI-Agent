# T017: Finance: JV waterfall, exit, hold vs. sell

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M1: Domain and finance core |
| Depends on | T016 |
| Read first | SPEC §6 |
| Allowed to modify | `src/cre_brain/finance/waterfall.py`, `src/cre_brain/finance/exit.py`, `src/cre_brain/finance/holdsell.py`, `tests/finance/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Equity structures and disposition analysis.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t017_ac<n>_*`.
- [ ] AC1 (`test_t017_ac1_*`): Waterfall: pref, IRR hurdles, catch-up, promote tiers on dated flows; tiers sum to total (property test)
- [ ] AC2 (`test_t017_ac2_*`): Exit value by cap rate with selling costs
- [ ] AC3 (`test_t017_ac3_*`): Hold-vs-sell and refi scenario comparison
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/finance -q -k 'waterfall or exit or holdsell' && uv run python scripts/check_task.py T017
```

## Done when
All ACs are met, verify exits 0, `passes` for T017 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
