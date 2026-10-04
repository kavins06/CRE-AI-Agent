# T092: Three-layer memory and retrieval

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M7: Firms and memory |
| Depends on | T091 |
| Read first | SPEC §13 |
| Allowed to modify | `src/cre_brain/memory/**`, `tests/memory/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`, `src/cre_brain/memory/sanitize.py`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Global/firm/user memory.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t092_ac<n>_*`.
- [ ] AC1 (`test_t092_ac1_*`): Stores + access control; firm A never retrieves firm B (test)
- [ ] AC2 (`test_t092_ac2_*`): Retrieval into segment AGENTS.md within token cap
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/memory -q && uv run python scripts/check_task.py T092
```

## Done when
All ACs are met, verify exits 0, `passes` for T092 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
