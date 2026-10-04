# T060: Ask-and-continue, messages, revisions

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M4: Full analyst deliverables |
| Depends on | T040, T012 |
| Read first | SPEC §10.5 |
| Allowed to modify | `src/cre_brain/runner/**`, `tests/runner/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Questions with defaults, answers → stale → regenerate.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t060_ac<n>_*`.
- [ ] AC1 (`test_t060_ac1_*`): ask_user records default Assumption + edges; continues
- [ ] AC2 (`test_t060_ac2_*`): Answer or user message → mark_stale → resume segment regenerating stale items
- [ ] AC3 (`test_t060_ac3_*`): Question suite H runs (FakeRunner in CI; live via make eval)
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/runner -q -k ask && uv run python scripts/check_task.py T060
```

## Done when
All ACs are met, verify exits 0, `passes` for T060 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
