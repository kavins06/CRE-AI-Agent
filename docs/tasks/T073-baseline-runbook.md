# T073: Baseline report and runbook

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M6: Connectors and portability (branch `milestone/M6`) |
| Depends on | T065, T041 |
| Read first | EVALS §5 |
| Allowed to modify | `docs/BASELINE.md`, `docs/RUNBOOK.md`, `evals/reports/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Document where the analyst stands and how to operate it.

## Acceptance criteria
- [ ] AC1: `docs/BASELINE.md`: scores per deliverable vs. the bars, cost, latency, top failure categories
- [ ] AC2: `docs/RUNBOOK.md`: deploy, keys, nightly learning, rollback, adding a firm, adding real deals
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
test -f docs/BASELINE.md && test -f docs/RUNBOOK.md && make check
```

## Done when
All ACs are met, verify exits 0, `passes` for T073 is set to true, the task branch is merged into `milestone/M6`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
