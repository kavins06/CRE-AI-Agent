# T101: Jev decision model

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M8: Connectors, Jev, SDK runners, baseline |
| Depends on | T068 |
| Read first | LIBRARY_NOTES typesafe-sdk |
| Allowed to modify | `src/cre_brain/decisions/**`, `tests/decisions/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Optional fast typed decisions.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t101_ac<n>_*`.
- [ ] AC1 (`test_t101_ac1_*`): JevDecisionModel behind DecisionModel; used only if key exists AND calibrated on labelled cases; requires_key(TYPESAFE_API_KEY)
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/decisions -q -k jev && uv run python scripts/check_task.py T101
```

## Done when
All ACs are met, verify exits 0, `passes` for T101 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
