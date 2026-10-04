# T061: Owner labelling queue and advisory judges

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M4: Full analyst deliverables |
| Depends on | T041 |
| Read first | EVALS §3 |
| Allowed to modify | `evals/judges/**`, `src/cre_brain/cli_label.py`, `tests/evals/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
Make judge calibration possible.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t061_ac<n>_*`.
- [ ] AC1 (`test_t061_ac1_*`): `cre label` serves a queue of binary rubric items for the owner; labels stored for the private repo
- [ ] AC2 (`test_t061_ac2_*`): Judge = separate Codex verifier session; TPR/TNR + Rogan-Gladen report; cannot gate below 150 labels/item
- [ ] AC3 (`test_t061_ac3_*`): Anchor-set drift check
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/evals -q -k judge && uv run python scripts/check_task.py T061
```

## Done when
All ACs are met, verify exits 0, `passes` for T061 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
