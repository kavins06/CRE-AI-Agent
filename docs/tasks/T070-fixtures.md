# T070: Frozen per-deliverable fixtures

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M5: Learning loop (overnight self-improvement) |
| Depends on | T041 |
| Read first | LEARNING §3 |
| Allowed to modify | `learning/fixtures/**`, `tests/learning/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Checkpoint deal states just before each deliverable kind.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t070_ac<n>_*`.
- [ ] AC1 (`test_t070_ac1_*`): `cre fixtures build --kind K --n 10` from dev packages; `cre fixtures check`
- [ ] AC2 (`test_t070_ac2_*`): Fixtures are immutable and hashed
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/learning -q -k fixtures && uv run python scripts/check_task.py T070
```

## Done when
All ACs are met, verify exits 0, `passes` for T070 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
