# T068: DecisionModel: rules + Codex classifier

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M4: Full analyst deliverables |
| Depends on | T033 |
| Read first | SPEC §2 |
| Allowed to modify | `src/cre_brain/decisions/**`, `tests/decisions/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Fast typed decisions.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t068_ac<n>_*`.
- [ ] AC1 (`test_t068_ac1_*`): RuleDecisionModel heuristics for doc types/routing
- [ ] AC2 (`test_t068_ac2_*`): CodexDecisionModel one-shot classifier with output schema when rules are unsure; calibration script
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/decisions -q && uv run python scripts/check_task.py T068
```

## Done when
All ACs are met, verify exits 0, `passes` for T068 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
