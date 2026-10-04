# T032: CRE tool server (MCP + CLI) and policy

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M2: First working analyst (thin slice: SCREEN + UW_MODEL via cre run) |
| Depends on | T012, T018, T020, T021, T030 |
| Read first | SPEC §10.3–10.4 |
| Allowed to modify | `src/cre_brain/runner/tools/**`, `src/cre_brain/runner/policy.py`, `tests/runner/**`, `tests/protected/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | Yes. The milestone PR needs the owner's `protected-change` label |

## Goal
One registry exposing tools via `cre mcp serve` and `cre tool <name>`.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t032_ac<n>_*`.
- [ ] AC1 (`test_t032_ac1_*`): Core tools for the slice: facts_get/put, assumption_set, finance_run, excel_build, excel_recalc_parity, rules_eval, ask_user, finalize_deliverable, draft_external, send_external
- [ ] AC2 (`test_t032_ac2_*`): policy.py: toggles off|ask|on (ask returns pending_confirmation, never blocks), budgets, finalize runs gates and refuses with failures
- [ ] AC3 (`test_t032_ac3_*`): MCP and CLI produce identical JSON for the same call (test)
- [ ] AC4 (`test_t032_ac4_*`): Contract tests in tests/protected/test_policy_contract.py
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/runner -q -k tools && uv run pytest tests/protected -q -k policy && uv run python scripts/check_task.py T032
```

## Done when
All ACs are met, verify exits 0, `passes` for T032 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
