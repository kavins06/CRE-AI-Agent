# T065: Rent comp analysis and debt quote summary

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M4: Full analyst deliverables |
| Depends on | T039, T015 |
| Read first | SPEC §6.6 |
| Allowed to modify | `src/cre_brain/deliverables/comps/**`, `src/cre_brain/deliverables/debt/**`, `brain/skills/**`, `tests/deliverables/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Comps (honest proxies) and financing comparison.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t065_ac<n>_*`.
- [ ] AC1 (`test_t065_ac1_*`): Comp selection/adjustment on provided or synthetic comp sets; proxies labelled
- [ ] AC2 (`test_t065_ac2_*`): Debt quote summary from extracted term sheets via finance.debt comparison
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/deliverables -q -k 'comps or debtquote' && uv run python scripts/check_task.py T065
```

## Done when
All ACs are met, verify exits 0, `passes` for T065 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
