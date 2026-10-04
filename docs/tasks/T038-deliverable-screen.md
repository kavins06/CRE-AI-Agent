# T038: SCREEN deliverable

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M2: First working analyst (thin slice: SCREEN + UW_MODEL via cre run) |
| Depends on | T035, T037 |
| Read first | SPEC §10.6 |
| Allowed to modify | `src/cre_brain/deliverables/screen/**`, `brain/skills/screen/**`, `brain/prompts/**`, `tests/deliverables/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Screen-first fast path.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t038_ac<n>_*`.
- [ ] AC1 (`test_t038_ac1_*`): Classify docs (rules first), headline extraction, buy-box, memo (Markdown + JSON) with risk_score CalcResult
- [ ] AC2 (`test_t038_ac2_*`): Skill `brain/skills/screen/SKILL.md`; finalize passes gates on generator fixtures (FakeRunner)
- [ ] AC3 (`test_t038_ac3_*`): Latency recorded per run
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/deliverables -q -k screen && uv run python scripts/check_task.py T038
```

## Done when
All ACs are met, verify exits 0, `passes` for T038 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
