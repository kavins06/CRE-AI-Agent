# T075: Nightly run, releases, rollback

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M5: Learning loop (overnight self-improvement) |
| Depends on | T073, T004 |
| Read first | LEARNING §8 |
| Allowed to modify | `learning/nightly.py`, `src/cre_brain/release/**`, `tests/learning/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Unattended improvement.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t075_ac<n>_*`.
- [ ] AC1 (`test_t075_ac1_*`): `cre learn nightly` rotates kinds by gap, respects nightly_sessions/wallclock, SKIPPED_NO_RUNNER when Codex unusable
- [ ] AC2 (`test_t075_ac2_*`): Weekly end-to-end non-inferiority; rollback tested; PR + PROGRESS entry
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/learning -q -k nightly && uv run python scripts/check_task.py T075
```

## Done when
All ACs are met, verify exits 0, `passes` for T075 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
