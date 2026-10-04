# T033: Hooks: policy, budgets, quarantine, gates

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M3: Agent (branch `milestone/M3`) |
| Depends on | T032 |
| Read first | SPEC §10.3 |
| Allowed to modify | `src/cre_brain/runner/hooks.py`, `tests/runner/**`, `tests/protected/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
The enforcement layer that makes the rules hold in code.

## Acceptance criteria
- [ ] AC1: The PreToolUse policy blocks untoggled external actions, writes outside the allowed dirs, and non-allowlisted network
- [ ] AC2: Any tool call originating from an extraction subagent is denied
- [ ] AC3: Budget enforcement (turns, cost, wall-clock) → `BLOCKED` escalation
- [ ] AC4: The finalize hook runs the gates and denies with the failure list
- [ ] AC5: Contract tests in `tests/protected/test_hooks_contract.py` for every rule
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/runner -q -k hooks && uv run pytest tests/protected -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T033 is set to true, the task branch is merged into `milestone/M3`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
