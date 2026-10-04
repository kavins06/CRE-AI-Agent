# T032: CRE tool server

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M3: Agent (branch `milestone/M3`) |
| Depends on | T011, T013, T015, T016, T030 |
| Read first | SPEC §10.4 |
| Allowed to modify | `src/cre_brain/runner/tools/**`, `src/cre_brain/runner/policy.py`, `tests/runner/**`, `tests/protected/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
The `cre` tool server exposing every CRE tool as an MCP tool AND an identical `cre tool <name>` CLI command, with policy enforced inside the tools.

## Acceptance criteria
- [ ] AC1: All tools from SPEC §10.4 (incl. toggle-gated `browse`) implemented once, exposed via `cre mcp serve` and `cre tool ...`, concise JSON and actionable errors
- [ ] AC2: `runner/policy.py` enforced inside tools: toggles off/ask/on (ask emits `confirmation_request` and waits), budgets, `finalize_deliverable` runs gates and refuses with failures
- [ ] AC3: `send_external` refuses unless toggle is `on` (or `ask` + approved); `draft_external` writes to `outbox/`; contract tests in `tests/protected/test_policy_contract.py`
- [ ] AC4: Each tool has unit tests + one FakeRunner transcript exercising it
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/runner -q -k tools
```

## Done when
All ACs are met, verify exits 0, `passes` for T032 is set to true, the task branch is merged into `milestone/M3`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
