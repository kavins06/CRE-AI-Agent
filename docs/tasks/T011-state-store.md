# T011: State store and dependency invalidation

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M1: Domain core (branch `milestone/M1`) |
| Depends on | T010 |
| Read first | SPEC §5 |
| Allowed to modify | `src/cre_brain/state/**`, `migrations/**`, `tests/state/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
A versioned state store with a dependency graph and stale propagation.

## Acceptance criteria
- [ ] AC1: SQLAlchemy/SQLModel tables per SPEC §5 with Alembic migrations; SQLite by default, Postgres URL supported
- [ ] AC2: Facts are append-only versions; a `current` view or query returns the latest
- [ ] AC3: `graph.add_edge`, `graph.mark_stale(id)` (transitive) and `graph.stale_items(deal_id)` (topological order)
- [ ] AC4: Test: changing one unit's rent marks the NOI calc, UW model, IC memo and LOI stale, and nothing unrelated
- [ ] AC5: The `events` table is append-only with `emit()` and `replay(task_id)`
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/state -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T011 is set to true, the task branch is merged into `milestone/M1`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
