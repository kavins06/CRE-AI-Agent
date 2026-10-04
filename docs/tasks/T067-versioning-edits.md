# T067: Deliverable versioning and user-edit ingestion

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M4: Full analyst deliverables |
| Depends on | T039, T011 |
| Read first | SPEC §4 |
| Allowed to modify | `src/cre_brain/deliverables/versioning.py`, `src/cre_brain/runner/tools/**`, `tests/deliverables/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Round-trip user edits.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t067_ac<n>_*`.
- [ ] AC1 (`test_t067_ac1_*`): Every regeneration = new version, old superseded
- [ ] AC2 (`test_t067_ac2_*`): `ingest_user_edit` diffs an uploaded Excel/memo vs parent → Correction records (fact/assumption/convention)
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/deliverables -q -k versioning && uv run python scripts/check_task.py T067
```

## Done when
All ACs are met, verify exits 0, `passes` for T067 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
