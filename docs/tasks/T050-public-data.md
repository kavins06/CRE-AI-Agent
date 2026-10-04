# T050: Public data clients

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M3: Evals on real anchors |
| Depends on | T003 |
| Read first | DATA_SOURCES |
| Allowed to modify | `src/cre_brain/data/**`, `tests/data/**`, `tests/fixtures/data/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Cached, rate-limited clients with recorded HTTP fixtures.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t050_ac<n>_*`.
- [ ] AC1 (`test_t050_ac1_*`): EDGAR (SEC_USER_AGENT, ≤8 rps), FRED, ACS, HUD, BLS, Cook County; disk cache; vcrpy fixtures
- [ ] AC2 (`test_t050_ac2_*`): Missing key → requires_key skip in tests, SKIPPED_NO_KEY at runtime
- [ ] AC3 (`test_t050_ac3_*`): Field names marked [U] verified when keys exist; DATA_SOURCES updated
- [ ] AC4 (`test_t050_ac4_*`): Generator priors calibrated from these sources (`cre evals calibrate-priors`)
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/data -q && uv run python scripts/check_task.py T050
```

## Done when
All ACs are met, verify exits 0, `passes` for T050 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
