# T072: Keep rule with statistical validation

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M5: Learning loop (overnight self-improvement) |
| Depends on | T070 |
| Read first | LEARNING §5 |
| Allowed to modify | `learning/keep_rule.py`, `tests/protected/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
A keep rule that noise cannot fool.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t072_ac<n>_*`.
- [ ] AC1 (`test_t072_ac1_*`): Paired bootstrap, Bonferroni per night, counter-metric tolerances, simplicity tie-break
- [ ] AC2 (`test_t072_ac2_*`): Simulation: null false-keep ≤1% (95% upper bound ≤1.5%) over 2,000 experiments at n=10,k=3,SD 0.15; power ≥80% at +0.10; otherwise reports minimum n
- [ ] AC3 (`test_t072_ac3_*`): Tests use fixed seeds AND a randomized-seed run
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/protected -q -k keep_rule && uv run python scripts/check_task.py T072
```

## Done when
All ACs are met, verify exits 0, `passes` for T072 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
