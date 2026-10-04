# T062: IC_MEMO deliverable

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M4: Full analyst deliverables |
| Depends on | T039, T037 |
| Read first | SPEC §11 |
| Allowed to modify | `src/cre_brain/deliverables/icmemo/**`, `brain/skills/ic-memo/**`, `brain/prompts/**`, `tests/deliverables/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
IC memo with full number provenance.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t062_ac<n>_*`.
- [ ] AC1 (`test_t062_ac1_*`): Sections per required_sections; every number provenance-checked; JV waterfall section when equity structure provided
- [ ] AC2 (`test_t062_ac2_*`): Advisory entailment/verifier results attached
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/deliverables -q -k icmemo && uv run python scripts/check_task.py T062
```

## Done when
All ACs are met, verify exits 0, `passes` for T062 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
