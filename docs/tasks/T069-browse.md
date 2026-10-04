# T069: Browse tool (toggle-gated)

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M4: Full analyst deliverables |
| Depends on | T032, T031 |
| Read first | SPEC §10.4 |
| Allowed to modify | `src/cre_brain/runner/tools/browse.py`, `tests/runner/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Web research as untrusted input.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t069_ac<n>_*`.
- [ ] AC1 (`test_t069_ac1_*`): Playwright in box, egress allowlist, toggle off|ask|on
- [ ] AC2 (`test_t069_ac2_*`): Results stored as Facts with provenance and treated as untrusted; adversarial web cases pass
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/runner -q -k browse && uv run python scripts/check_task.py T069
```

## Done when
All ACs are met, verify exits 0, `passes` for T069 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
