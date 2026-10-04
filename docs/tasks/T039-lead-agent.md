# T039: Lead agent orchestration

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M3: Agent (branch `milestone/M3`) |
| Depends on | T037, T038 |
| Read first | SPEC §10.1, §10.5; METHOD §3.3 |
| Allowed to modify | `src/cre_brain/runner/**`, `brain/prompts/lead.md`, `tests/runner/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Task-driven planning, ask-and-continue, revision on answers, escalation.

## Acceptance criteria
- [ ] AC1: The lead prompt is assembled per SPEC §10.1; the agent writes `todo.md` and selects deliverables from the request
- [ ] AC2: `ask_user` → default recorded → continues; on answer, stale items are regenerated (SPEC §10.5)
- [ ] AC3: ESCALATION deliverable when blocked or out of budget
- [ ] AC4: Task-request suite G and question suite H run via FakeRunner in CI; live scores recorded when a key exists
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/runner -q -k lead && make eval SUITE=questions_smoke
```

## Done when
All ACs are met, verify exits 0, `passes` for T039 is set to true, the task branch is merged into `milestone/M3`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
