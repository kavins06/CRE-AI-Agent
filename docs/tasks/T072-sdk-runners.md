# T072: Commercial SDK runners: Claude Agent SDK and OpenAI

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M6: Connectors and portability (branch `milestone/M6`) |
| Depends on | T041 |
| Read first | METHOD §3.1; LIBRARY_NOTES claude-agent-sdk |
| Allowed to modify | `src/cre_brain/runner/**`, `brain/prompts/overlays/**`, `tests/runner/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Add production runners sharing the same tools, policy and gates, and compare them on evals.

## Acceptance criteria
- [ ] AC1: `ClaudeRunner` (claude-agent-sdk) and `OpenAIAgentsRunner` implement `Runner`, using the same `cre` MCP tool server and policy; SDK hooks mirror policy as defence in depth
- [ ] AC2: Per-runner prompt overlays in `brain/prompts/overlays/<runner>/`
- [ ] AC3: `cre evals compare-runners` produces a side-by-side report across Codex, Claude and OpenAI runners (skips without keys)
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/runner -q -k 'claude or openai'
```

## Done when
All ACs are met, verify exits 0, `passes` for T072 is set to true, the task branch is merged into `milestone/M6`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
