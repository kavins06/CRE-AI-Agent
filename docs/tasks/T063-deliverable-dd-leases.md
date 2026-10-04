# T063: DD tracker, issues log, lease abstracts

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M4: Full analyst deliverables |
| Depends on | T035, T054, T037 |
| Read first | SPEC §11 |
| Allowed to modify | `src/cre_brain/deliverables/dd/**`, `src/cre_brain/deliverables/lease/**`, `brain/skills/**`, `tests/deliverables/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Diligence deliverables.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t063_ac<n>_*`.
- [ ] AC1 (`test_t063_ac1_*`): Extraction schemas for leases, amendments, estoppels, third-party reports
- [ ] AC2 (`test_t063_ac2_*`): DD checklist status + issues log with provenance; lease abstracts with amendment-chain resolution
- [ ] AC3 (`test_t063_ac3_*`): Rent-regulation rule check
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/deliverables -q -k 'dd or lease' && uv run python scripts/check_task.py T063
```

## Done when
All ACs are met, verify exits 0, `passes` for T063 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
