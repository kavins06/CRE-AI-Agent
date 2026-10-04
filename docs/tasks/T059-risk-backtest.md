# T059: Risk score AUROC backtest

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M3: Evals on real anchors |
| Depends on | T051, T039 |
| Read first | EVALS §3 |
| Allowed to modify | `evals/backtest/**`, `tests/evals/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
Does the analyst's risk_score rank outcomes better than DSCR/LTV?

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t059_ac<n>_*`.
- [ ] AC1 (`test_t059_ac1_*`): Compute AUROC of risk_score vs. baseline against EX-102 outcomes (delinquency, special servicing, NOI −10% in 24–36 mo)
- [ ] AC2 (`test_t059_ac2_*`): Report with and without likely-memorized vintages
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/evals -q -k backtest && uv run python scripts/check_task.py T059
```

## Done when
All ACs are met, verify exits 0, `passes` for T059 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
