# T019: Excel reference template and writer

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M1: Domain and finance core |
| Depends on | T018 |
| Read first | SPEC §7 |
| Allowed to modify | `src/cre_brain/excel/**`, `tests/excel/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Code-generated MF template + map + writer.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t019_ac<n>_*`.
- [ ] AC1 (`test_t019_ac1_*`): `build_template.py` generates `templates/mf_standard.xlsx` with whitelisted functions only and no circular refs; named ranges
- [ ] AC2 (`test_t019_ac2_*`): `mf_standard.map.json` maps calc ids/fact keys ↔ cells
- [ ] AC3 (`test_t019_ac3_*`): Writer fills inputs from state; test asserts only whitelisted functions in formulas
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/excel -q -k template && uv run python scripts/check_task.py T019
```

## Done when
All ACs are met, verify exits 0, `passes` for T019 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
