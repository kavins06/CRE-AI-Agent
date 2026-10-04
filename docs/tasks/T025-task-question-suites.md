# T025: Task-request and question-handling suites

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M2: Data and evals (branch `milestone/M2`) |
| Depends on | T022 |
| Read first | EVALS §2 sets G and H |
| Allowed to modify | `evals/suites/**`, `tests/evals/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Suites that test task-driven planning and ask-and-continue behavior.

## Acceptance criteria
- [ ] AC1: ≥100 varied user requests mapped to an expected deliverable plan
- [ ] AC2: ≥60 question scenarios, each with the expected question topic, an acceptable default range, and the expected revised outputs after the scripted answer
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/evals -q -k suites
```

## Done when
All ACs are met, verify exits 0, `passes` for T025 is set to true, the task branch is merged into `milestone/M2`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
