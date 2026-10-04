# T055: Defect injector

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M3: Evals on real anchors |
| Depends on | T054 |
| Read first | EVALS §2 defect list |
| Allowed to modify | `evals/defects/**`, `tests/evals/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
All 30 defects × 3 magnitudes + clean controls.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t055_ac<n>_*`.
- [ ] AC1 (`test_t055_ac1_*`): Each defect with label schema (type, location, magnitude, severity) and a deterministic oracle test
- [ ] AC2 (`test_t055_ac2_*`): 20% clean controls
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/evals -q -k defects && uv run python scripts/check_task.py T055
```

## Done when
All ACs are met, verify exits 0, `passes` for T055 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
