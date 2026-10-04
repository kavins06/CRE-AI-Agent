# T034: Deterministic document pre-parsing

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M2: First working analyst (thin slice: SCREEN + UW_MODEL via cre run) |
| Depends on | T010 |
| Read first | SPEC §10.2 |
| Allowed to modify | `src/cre_brain/extraction/preparse/**`, `tests/extraction/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Turn raw files into parsed JSON with anchors.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t034_ac<n>_*`.
- [ ] AC1 (`test_t034_ac1_*`): XLSX/CSV read natively as cells with sheet/cell anchors
- [ ] AC2 (`test_t034_ac2_*`): PDF via Docling with page + bbox (origin normalized to top-left)
- [ ] AC3 (`test_t034_ac3_*`): Reducto adapter stub with requires_license(REDUCTO); output schema `parsed/<doc>.json`
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/extraction -q -k preparse && uv run python scripts/check_task.py T034
```

## Done when
All ACs are met, verify exits 0, `passes` for T034 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
