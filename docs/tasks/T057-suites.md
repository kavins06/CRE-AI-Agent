# T057: Task-request and question suites

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M3: Evals on real anchors |
| Depends on | T054 |
| Read first | EVALS §2 G, H |
| Allowed to modify | `evals/suites/**`, `tests/evals/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
Planning and ask-and-continue suites.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t057_ac<n>_*`.
- [ ] AC1 (`test_t057_ac1_*`): ≥100 requests → expected deliverable plans (incl. multi-deal)
- [ ] AC2 (`test_t057_ac2_*`): ≥60 question scenarios with expected question, default range, scripted answer, expected revision
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/evals -q -k suites && uv run python scripts/check_task.py T057
```

## Done when
All ACs are met, verify exits 0, `passes` for T057 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
