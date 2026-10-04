# T033: Stuck detection and event redaction

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M3: Agent (branch `milestone/M3`) |
| Depends on | T032 |
| Read first | SPEC §10.3, §15 |
| Allowed to modify | `src/cre_brain/runner/stuck.py`, `src/cre_brain/runner/redact.py`, `tests/runner/**`, `tests/protected/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Runner-agnostic loop detection and secret redaction on every event.

## Acceptance criteria
- [ ] AC1: Stuck detector over the AgentEvent stream: repeated identical tool call+result, repeated errors, no-progress turns → one nudge, then stop segment and emit ESCALATION + `stuck` event
- [ ] AC2: Redaction applied before events are stored or streamed: registered secrets, credentials, tokens masked; planted-secret tests 100% caught
- [ ] AC3: Contract tests in `tests/protected/` for stuck and redaction rules
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/runner -q -k 'stuck or redact' && uv run pytest tests/protected -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T033 is set to true, the task branch is merged into `milestone/M3`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
