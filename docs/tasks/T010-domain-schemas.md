# T010: Domain schemas incl. AgentEvent

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M1: Domain and finance core |
| Depends on | T001 |
| Read first | SPEC §4 |
| Allowed to modify | `src/cre_brain/domain/**`, `tests/domain/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
All Pydantic v2 models in SPEC §4.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t010_ac<n>_*`.
- [ ] AC1 (`test_t010_ac1_*`): Fact, Provenance, ClaimType, Assumption, CalcResult, Question, Deliverable (versioned, deal_ids list, edited_by_user), Task (deal_ids list), AgentEvent (seq assigned by control plane, origin tuple, full kind list) exactly as SPEC §4
- [ ] AC2 (`test_t010_ac2_*`): DeliverableKind includes RENT_COMP_ANALYSIS and DEBT_QUOTE_SUMMARY
- [ ] AC3 (`test_t010_ac3_*`): JSON round-trip tests; hypothesis strategies exported
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/domain -q && uv run python scripts/check_task.py T010
```

## Done when
All ACs are met, verify exits 0, `passes` for T010 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
