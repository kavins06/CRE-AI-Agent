# T020: Recalculation and parity

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M1: Domain and finance core |
| Depends on | T019 |
| Read first | SPEC §7; LIBRARY_NOTES LibreOffice |
| Allowed to modify | `src/cre_brain/excel/**`, `tests/excel/**`, `docker/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
LibreOffice (unoserver) recalc and Python parity.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t020_ac<n>_*`.
- [ ] AC1 (`test_t020_ac1_*`): LibreOfficeEngine via Python UNO/unoserver (fallback macro), one profile per worker; output keeps formulas + cached values and is the deliverable
- [ ] AC2 (`test_t020_ac2_*`): Parity diff within gates.yaml tolerances; error scan for #REF!/#DIV/0!/#VALUE!/#NAME?
- [ ] AC3 (`test_t020_ac3_*`): Asserts recalculated values are not None (no silent no-op)
- [ ] AC4 (`test_t020_ac4_*`): Synthetic deal → PASS; planted formula error → FAIL with cell address; GraphExcelEngine stub skipped with requires_license(MS_GRAPH)
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/excel -q && uv run python scripts/check_task.py T020
```

## Done when
All ACs are met, verify exits 0, `passes` for T020 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
