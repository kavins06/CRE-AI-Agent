# T091: Firm buy-box and memo style

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M7: Firms and memory |
| Depends on | T090, T021 |
| Read first | SPEC §14 |
| Allowed to modify | `src/cre_brain/onboarding/**`, `tests/onboarding/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Criteria and voice.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t091_ac<n>_*`.
- [ ] AC1 (`test_t091_ac1_*`): Buy-box text/form → JDM tables + generated rule tests from firm-confirmed examples
- [ ] AC2 (`test_t091_ac2_*`): Memo style guide from samples → firms/<id>/playbook/memo_style.md
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/onboarding -q -k 'policy or style' && uv run python scripts/check_task.py T091
```

## Done when
All ACs are met, verify exits 0, `passes` for T091 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
