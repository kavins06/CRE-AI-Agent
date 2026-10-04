# T030: Claude Agent SDK spike + FakeRunner

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M3: Agent (branch `milestone/M3`) |
| Depends on | T003 |
| Read first | SPEC §10; LIBRARY_NOTES claude-agent-sdk |
| Allowed to modify | `src/cre_brain/runner/**`, `tests/runner/**`, `docs/LIBRARY_NOTES.md`, `tests/fixtures/transcripts/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Prove every SDK feature we depend on and build the replay runner.

## Acceptance criteria
- [ ] AC1: A minimal ClaudeSDKClient session with: one in-process `@tool`, one PreToolUse deny hook, one subagent with `tools=[]` + structured output, Skills loading, a session resume
- [ ] AC2: Every [verify] item in LIBRARY_NOTES for claude-agent-sdk is confirmed or corrected (docs updated in this PR)
- [ ] AC3: `Runner` protocol + `FakeRunner` that replays a recorded JSONL transcript against real tools
- [ ] AC4: `cre record` records a transcript when `ANTHROPIC_API_KEY` exists; otherwise logs `SKIPPED_NO_KEY`
- [ ] AC5: Tests run fully offline with FakeRunner
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/runner -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T030 is set to true, the task branch is merged into `milestone/M3`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
