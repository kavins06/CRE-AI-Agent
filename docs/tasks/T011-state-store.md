# T011: State store (versioned, Postgres/SQLite)

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M1: Domain and finance core |
| Depends on | T010 |
| Read first | SPEC §5 |
| Allowed to modify | `src/cre_brain/state/**`, `migrations/**`, `tests/state/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Append-only versioned store with Alembic migrations.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t011_ac<n>_*`.
- [ ] AC1 (`test_t011_ac1_*`): Tables per SPEC §5 incl. jobs and corrections; Postgres in integration tests (docker compose), SQLite in unit tests
- [ ] AC2 (`test_t011_ac2_*`): Facts/deliverables append-only; `current()` queries latest version
- [ ] AC3 (`test_t011_ac3_*`): Events table assigns per-task monotonic `seq` on insert and de-duplicates by `origin`
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/state -q -m 'not integration' && uv run python scripts/check_task.py T011
```

## Done when
All ACs are met, verify exits 0, `passes` for T011 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
