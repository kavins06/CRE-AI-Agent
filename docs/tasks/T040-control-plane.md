# T040: Control plane: API, DBOS workflow, events

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M3: Agent (branch `milestone/M3`) |
| Depends on | T039, T042 |
| Read first | SPEC §12; LIBRARY_NOTES DBOS |
| Allowed to modify | `src/cre_brain/control/**`, `clients/ts/**`, `tests/control/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Durable task execution and the API the owner's UI will call.

## Acceptance criteria
- [ ] AC1: All FastAPI endpoints from SPEC §12 incl. messages, interrupt, pause, resume, confirmations, paged events, SSE with Last-Event-ID
- [ ] AC2: Auth on every route with user_id/firm_id claims; API isolation test (user A gets 404 on user B task)
- [ ] AC3: OpenAPI published; typed TypeScript client generated into `clients/ts/`
- [ ] AC4: A DBOS workflow per task with step keys (task_id, segment_no); a killed worker resumes from its last completed step without starting a duplicate session (test)
- [ ] AC5: Budget meter per task and user
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/control -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T040 is set to true, the task branch is merged into `milestone/M3`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
