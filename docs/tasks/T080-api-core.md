# T080: Control-plane API core with auth

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M6: Platform (API, box agent, recovery, stress) |
| Depends on | T040 |
| Read first | SPEC §12 |
| Allowed to modify | `src/cre_brain/control/**`, `tests/control/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Authenticated, tenant-scoped API.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t080_ac<n>_*`.
- [ ] AC1 (`test_t080_ac1_*`): Routes: tasks, deliverables (versions), corrections, toggles
- [ ] AC2 (`test_t080_ac2_*`): Token claims user_id/firm_id; parameterized isolation test over EVERY route
- [ ] AC3 (`test_t080_ac3_*`): Postgres integration tests
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/control -q -k api && uv run python scripts/check_task.py T080
```

## Done when
All ACs are met, verify exits 0, `passes` for T080 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
