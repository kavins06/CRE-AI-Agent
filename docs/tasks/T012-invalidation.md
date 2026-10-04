# T012: Dependency graph and stale propagation

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M1: Domain and finance core |
| Depends on | T011 |
| Read first | SPEC §5 |
| Allowed to modify | `src/cre_brain/state/graph.py`, `tests/state/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Transitive invalidation with stale events.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t012_ac<n>_*`.
- [ ] AC1 (`test_t012_ac1_*`): `add_edge`, `mark_stale` (transitive, emits `stale` events), `stale_items(task)` in topological order
- [ ] AC2 (`test_t012_ac2_*`): Rent change on one unit marks NOI calc, UW model, IC memo, LOI stale and nothing unrelated
- [ ] AC3 (`test_t012_ac3_*`): Cycle detection raises
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/state -q -k graph && uv run python scripts/check_task.py T012
```

## Done when
All ACs are met, verify exits 0, `passes` for T012 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
