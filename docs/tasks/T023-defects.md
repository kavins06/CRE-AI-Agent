# T023: Defect injector

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M2: Data and evals (branch `milestone/M2`) |
| Depends on | T022 |
| Read first | EVALS §2 defect list |
| Allowed to modify | `evals/defects/**`, `tests/evals/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Inject the 30 defect types at 5 magnitudes, with labels and clean controls.

## Acceptance criteria
- [ ] AC1: All 30 defect types from EVALS §2 implemented, each with a label schema (type, location, magnitude, severity)
- [ ] AC2: 20% clean controls in generated sets
- [ ] AC3: Test per defect type: injected → detectable by its deterministic oracle
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/evals -q -k defects
```

## Done when
All ACs are met, verify exits 0, `passes` for T023 is set to true, the task branch is merged into `milestone/M2`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
