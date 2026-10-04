# T087: Stress tests

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M6: Platform (API, box agent, recovery, stress) |
| Depends on | T084, T082 |
| Read first | SPEC §12 |
| Allowed to modify | `tests/stress/**`, `reports/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Load and failure behaviour.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t087_ac<n>_*`.
- [ ] AC1 (`test_t087_ac1_*`): N concurrent tasks, slow SSE consumer, killed worker, dropped box; within latency/memory budgets (FakeRunner)
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/stress -q && uv run python scripts/check_task.py T087
```

## Done when
All ACs are met, verify exits 0, `passes` for T087 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
