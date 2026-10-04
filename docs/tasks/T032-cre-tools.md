# T032: CRE tool server

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M3: Agent (branch `milestone/M3`) |
| Depends on | T011, T013, T015, T016, T030 |
| Read first | SPEC §10.4 |
| Allowed to modify | `src/cre_brain/runner/tools/**`, `tests/runner/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
The in-process SDK MCP server exposing the CRE tools.

## Acceptance criteria
- [ ] AC1: Tools from SPEC §10.4 implemented with concise JSON outputs and actionable errors
- [ ] AC2: `send_external` refuses unless the user's toggle is on; `draft_external` writes to `outbox/`
- [ ] AC3: Each tool has unit tests + one FakeRunner transcript exercising it
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/runner -q -k tools
```

## Done when
All ACs are met, verify exits 0, `passes` for T032 is set to true, the task branch is merged into `milestone/M3`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
