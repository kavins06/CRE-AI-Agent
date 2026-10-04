# T016: Finance: returns with multi-IRR handling

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M1: Domain and finance core |
| Depends on | T015 |
| Read first | SPEC §6 |
| Allowed to modify | `src/cre_brain/finance/returns.py`, `tests/finance/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
IRR/XIRR that never hides ambiguity.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t016_ac<n>_*`.
- [ ] AC1 (`test_t016_ac1_*`): Root bracketing in (-0.99, 10): 0 roots → undefined, >1 → ambiguous with roots + MIRR fallback
- [ ] AC2 (`test_t016_ac2_*`): NPV Excel convention (`start_from_zero=False`) matches Excel examples
- [ ] AC3 (`test_t016_ac3_*`): Property: NPV at each reported IRR ≈ 0; equity multiple and cash-on-cash
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/finance -q -k returns && uv run python scripts/check_task.py T016
```

## Done when
All ACs are met, verify exits 0, `passes` for T016 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
