# T030: Codex CLI runner spike + FakeRunner

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol in `AGENTS.md`.

| | |
|---|---|
| Milestone | M3: Agent (branch `milestone/M3`) |
| Depends on | T003, T010 |
| Read first | SPEC §9, §10.1–10.2; LIBRARY_NOTES Codex CLI |
| Allowed to modify | `src/cre_brain/runner/**`, `tests/runner/**`, `docs/LIBRARY_NOTES.md`, `tests/fixtures/transcripts/**`, `templates/codex/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Sealed paths (see AGENTS.md), other tasks' entries, existing tests' assertions |

## Goal
Prove every Codex CLI feature the analyst depends on, and build the runner abstraction plus the replay runner.

## Acceptance criteria
- [ ] AC1: `Runner` protocol; `CodexRunner` runs `codex exec --json` in a given working dir and normalizes the JSONL into `AgentEvent`s (raw kept as `runner_raw`)
- [ ] AC2: Spike proves each of these and records the result: an MCP tool call to a tiny test MCP server in non-interactive mode (find the narrowest approval setting; never the bypass flag outside a box), `--output-schema` structured output, `--sandbox read-only` with no MCP servers, session resume, AGENTS.md and `.agents/skills` pickup
- [ ] AC3: Every [verify] item for the Codex CLI in LIBRARY_NOTES is confirmed or corrected in this PR
- [ ] AC4: `templates/codex/config.toml` defines profiles `analyst`, `extractor`, `verifier`, `classifier` per SPEC §10
- [ ] AC5: `FakeRunner` replays a recorded JSONL transcript against real tools; `cre record` records one when the Codex CLI is available, else logs `SKIPPED_NO_RUNNER`
- [ ] AC6: Unit tests run fully offline with FakeRunner
- [ ] `make check` passes.

## Verify (must exit 0, paste the tail into PROGRESS.md)
```bash
uv run pytest tests/runner -q
```

## Done when
All ACs are met, verify exits 0, `passes` for T030 is set to true, the task branch is merged into `milestone/M3`, and a PROGRESS.md entry is written. If blocked, write a BLOCKED entry with evidence and move on.
