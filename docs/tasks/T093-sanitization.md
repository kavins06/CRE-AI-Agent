# T093: Sanitization gate

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M7: Firms and memory |
| Depends on | T092 |
| Read first | SPEC §13 |
| Allowed to modify | `src/cre_brain/memory/sanitize.py`, `tests/protected/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
Nothing firm-specific reaches global.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t093_ac<n>_*`.
- [ ] AC1 (`test_t093_ac1_*`): NER + deal-entity dictionary + number bucketing + quote removal; fails closed
- [ ] AC2 (`test_t093_ac2_*`): ≥50 planted leaks, 100% caught
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/protected -q -k sanitize && uv run python scripts/check_task.py T093
```

## Done when
All ACs are met, verify exits 0, `passes` for T093 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
