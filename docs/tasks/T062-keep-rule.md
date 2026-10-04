# T062: Keep rule statistics

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M5: Learning loop (branch `milestone/M5`) |
| Depends on | T060 |
| Read first | LEARNING §3 |
| Allowed to modify | `learning/keep_rule.py`, `tests/protected/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
A keep rule that cannot be fooled by noise.

## Acceptance criteria
- [ ] AC1: Paired bootstrap CI, Bonferroni per night, holdout confirmation, counter-metric tolerances, simplicity tie-break
- [ ] AC2: Test: 200 simulated nights of identical brains with seed noise → zero keeps; a true +5% effect is kept in most nights
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/protected -q -k keep_rule
```

## Done when
All ACs are met, verify exits 0, `passes` for T062 is set to true, the task branch is merged into `milestone/M5`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
