# T039: UW_MODEL deliverable

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M2: First working analyst (thin slice: SCREEN + UW_MODEL via cre run) |
| Depends on | T038 |
| Read first | SPEC §6–7, §11 |
| Allowed to modify | `src/cre_brain/deliverables/uw/**`, `brain/skills/underwrite/**`, `brain/prompts/**`, `tests/deliverables/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Python model + live-formula Excel with parity.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t039_ac<n>_*`.
- [ ] AC1 (`test_t039_ac1_*`): Assumptions set with ranges/rationale/proxy flags; Python model; Excel mirror (mf_standard) recalculated; parity; risk_score
- [ ] AC2 (`test_t039_ac2_*`): Value-add, tax reassessment, debt sizing included when inputs exist
- [ ] AC3 (`test_t039_ac3_*`): Skill `brain/skills/underwrite/SKILL.md`; gates pass on generator fixtures (FakeRunner)
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/deliverables -q -k uw && uv run python scripts/check_task.py T039
```

## Done when
All ACs are met, verify exits 0, `passes` for T039 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
