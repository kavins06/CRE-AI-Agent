# T074: Corrections (DAgger records)

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M5: Learning loop (overnight self-improvement) |
| Depends on | T067 |
| Read first | LEARNING §7 |
| Allowed to modify | `src/cre_brain/control/corrections.py`, `tests/control/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Every correction becomes signal.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t074_ac<n>_*`.
- [ ] AC1 (`test_t074_ac1_*`): `cre correct` + ingestion from user edits → DecisionRecord
- [ ] AC2 (`test_t074_ac2_*`): Exports private eval cases for the private repo; candidate lessons queued (no global promotion before M7)
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/control -q -k corrections && uv run python scripts/check_task.py T074
```

## Done when
All ACs are met, verify exits 0, `passes` for T074 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
