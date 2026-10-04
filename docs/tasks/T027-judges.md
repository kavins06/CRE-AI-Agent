# T027: Judge module with calibration

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M2: Data and evals (branch `milestone/M2`) |
| Depends on | T026 |
| Read first | EVALS §3 judge |
| Allowed to modify | `evals/judges/**`, `tests/evals/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Binary-rubric judges with calibration reporting.

## Acceptance criteria
- [ ] AC1: Rubric items as binary checks, with the judge model from the `verifier` role (different family when a key exists)
- [ ] AC2: `cre evals calibrate --item X` computes TPR/TNR against labels and a Rogan-Gladen corrected pass rate
- [ ] AC3: A judge cannot gate until it has ≥150 labels (enforced flag)
- [ ] AC4: 30-item anchor drift check
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/evals -q -k judge
```

## Done when
All ACs are met, verify exits 0, `passes` for T027 is set to true, the task branch is merged into `milestone/M2`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
