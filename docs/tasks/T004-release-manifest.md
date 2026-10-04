# T004: Brain Release manifest

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M0: Guards and scaffold |
| Depends on | T003 |
| Read first | LEARNING §8 |
| Allowed to modify | `src/cre_brain/release/**`, `tests/release/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Hash-identified, replayable releases.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t004_ac<n>_*`.
- [ ] AC1 (`test_t004_ac1_*`): `cre release build` writes `releases/<hash>.json` over brain/, config/*.yaml, gates code hash, runner/model ids, Codex CLI version (if available)
- [ ] AC2 (`test_t004_ac2_*`): `cre release list` and `cre release rollback <hash>`
- [ ] AC3 (`test_t004_ac3_*`): Changing one byte in brain/ changes the hash; rollback restores files
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/release -q && uv run python scripts/check_task.py T004
```

## Done when
All ACs are met, verify exits 0, `passes` for T004 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
