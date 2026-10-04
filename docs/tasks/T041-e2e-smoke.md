# T041: End-to-end smoke

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M3: Agent (branch `milestone/M3`) |
| Depends on | T040, T026 |
| Read first | EVALS §6 |
| Allowed to modify | `tests/e2e/**`, `evals/reports/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
A deal through the whole system.

## Acceptance criteria
- [ ] AC1: CI: a synthetic deal → POST /tasks → local Docker box → FakeRunner → deliverables + gates pass → events replayable
- [ ] AC2: Live (key present): the same with ClaudeRunner; latency and cost per deliverable recorded to `evals/reports/`
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/e2e -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T041 is set to true, the task branch is merged into `milestone/M3`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
