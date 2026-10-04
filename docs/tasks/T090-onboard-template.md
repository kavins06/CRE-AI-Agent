# T090: Firm template onboarding

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M7: Firms and memory |
| Depends on | T039 |
| Read first | SPEC §7, §14 |
| Allowed to modify | `src/cre_brain/onboarding/**`, `tests/onboarding/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Use each firm's Excel.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t090_ac<n>_*`.
- [ ] AC1 (`test_t090_ac1_*`): Feature scan (circular/iterative, data tables, .xlsm, external links, unsupported functions) → supported / needs_excel_engine / rejected with reasons
- [ ] AC2 (`test_t090_ac2_*`): Proposed cell map + parity on a synthetic deal through both templates; saved only if parity passes; tested on 2 differently structured templates
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/onboarding -q -k template && uv run python scripts/check_task.py T090
```

## Done when
All ACs are met, verify exits 0, `passes` for T090 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
