# T102: Commercial SDK runners

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M8: Connectors, Jev, SDK runners, baseline |
| Depends on | T041 |
| Read first | METHOD §3.1 |
| Allowed to modify | `src/cre_brain/runner/**`, `brain/prompts/overlays/**`, `tests/runner/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Claude Agent SDK and OpenAI runners on the same tools/policy/gates.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t102_ac<n>_*`.
- [ ] AC1 (`test_t102_ac1_*`): ClaudeRunner and OpenAIAgentsRunner implement Runner using the cre MCP server; SDK hooks mirror policy
- [ ] AC2 (`test_t102_ac2_*`): `cre evals compare-runners` side-by-side report (requires_key)
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/runner -q -k 'claude or openai' && uv run python scripts/check_task.py T102
```

## Done when
All ACs are met, verify exits 0, `passes` for T102 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
