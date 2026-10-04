# T094: ACE playbook queue and promotion

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M7: Firms and memory |
| Depends on | T093, T073 |
| Read first | LEARNING §6 |
| Allowed to modify | `src/cre_brain/memory/ace_queue.py`, `learning/**`, `tests/learning/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`, `learning/keep_rule.py`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Lessons proposed live, promoted through the ratchet.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t094_ac<n>_*`.
- [ ] AC1 (`test_t094_ac1_*`): Candidates from deterministic signals only; metadata; cap; contradiction check
- [ ] AC2 (`test_t094_ac2_*`): Promotion = sanitization + keep rule; live runs cannot write brain/playbook/global.md (test)
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/learning -q -k ace && uv run python scripts/check_task.py T094
```

## Done when
All ACs are met, verify exits 0, `passes` for T094 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
