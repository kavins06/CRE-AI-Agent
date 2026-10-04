# T085: Inbox ingestion

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M6: Platform (API, box agent, recovery, stress) |
| Depends on | T083 |
| Read first | SPEC §3 |
| Allowed to modify | `src/cre_brain/sandbox/boxd/**`, `tests/sandbox/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Dropped packages become tasks.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t085_ac<n>_*`.
- [ ] AC1 (`test_t085_ac1_*`): Watcher moves files to /srv/raw/<deal>, creates a task with optional request note; idempotent on re-drop
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/sandbox -q -k inbox && uv run python scripts/check_task.py T085
```

## Done when
All ACs are met, verify exits 0, `passes` for T085 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
