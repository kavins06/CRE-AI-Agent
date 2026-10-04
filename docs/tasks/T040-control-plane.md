# T040: Control plane: API, DBOS workflow, events

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M3: Agent (branch `milestone/M3`) |
| Depends on | T039, T031 |
| Read first | SPEC §12; LIBRARY_NOTES DBOS |
| Allowed to modify | `src/cre_brain/control/**`, `tests/control/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Durable task execution and the API the owner's UI will call.

## Acceptance criteria
- [ ] AC1: FastAPI endpoints from SPEC §12; SSE event stream; session replay from events
- [ ] AC2: A DBOS workflow per task; a killed worker resumes from its last completed step (test)
- [ ] AC3: Budget meter per task and user
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/control -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T040 is set to true, the task branch is merged into `milestone/M3`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
