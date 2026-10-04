# T073: Autoresearch experiment runner

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M5: Learning loop (overnight self-improvement) |
| Depends on | T071, T072, T058 |
| Read first | LEARNING §3; program.md |
| Allowed to modify | `learning/runner.py`, `tests/learning/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
program.md, implemented.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t073_ac<n>_*`.
- [ ] AC1 (`test_t073_ac1_*`): Branch autoresearch/<tag>; one artifact edit; k=3 paired dev eval in repo-less containers; keep_rule; holdout confirm via scoring service; results.tsv
- [ ] AC2 (`test_t073_ac2_*`): 3 h experiment kill; serialized when codex_login_max_concurrency=1
- [ ] AC3 (`test_t073_ac3_*`): Ends with PR → dev; never merges
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/learning -q -k runner && uv run python scripts/check_task.py T073
```

## Done when
All ACs are met, verify exits 0, `passes` for T073 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
