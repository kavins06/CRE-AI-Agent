# T066: Deal comparison and multi-deal tasks

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M4: Full analyst deliverables |
| Depends on | T039 |
| Read first | SPEC §4 |
| Allowed to modify | `src/cre_brain/deliverables/comparison/**`, `src/cre_brain/runner/**`, `tests/deliverables/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Tasks spanning several deals.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t066_ac<n>_*`.
- [ ] AC1 (`test_t066_ac1_*`): Task.deal_ids > 1 supported end to end
- [ ] AC2 (`test_t066_ac2_*`): DEAL_COMPARISON ranks deals on firm criteria with provenance
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/deliverables -q -k comparison && uv run python scripts/check_task.py T066
```

## Done when
All ACs are met, verify exits 0, `passes` for T066 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
