# T084: Box disk-loss recovery

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M6: Platform (API, box agent, recovery, stress) |
| Depends on | T083 |
| Read first | SPEC §10.8 |
| Allowed to modify | `src/cre_brain/sandbox/**`, `tests/sandbox/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Survive losing a box.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t084_ac<n>_*`.
- [ ] AC1 (`test_t084_ac1_*`): Fresh box rebuilt from state DB + todo snapshot; new segment with recovery message; recovery event (test kills box mid-task)
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/sandbox -q -k recovery && uv run python scripts/check_task.py T084
```

## Done when
All ACs are met, verify exits 0, `passes` for T084 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
