# T030: Codex CLI capability spike

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M2: First working analyst (thin slice: SCREEN + UW_MODEL via cre run) |
| Depends on | T003, T010 |
| Read first | SPEC §9–10; LIBRARY_NOTES Codex CLI |
| Allowed to modify | `src/cre_brain/runner/codex_probe.py`, `templates/codex/**`, `docs/LIBRARY_NOTES.md`, `tests/runner/**`, `PROGRESS.md`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Confirm every Codex behaviour we depend on, on the installed version; correct the docs.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t030_ac<n>_*`.
- [ ] AC1 (`test_t030_ac1_*`): `cre runner probe` checks and records: `codex exec --json` event shapes incl. usage; `--output-schema`; `--cd`; profiles; resume; AGENTS.md + `.agents/skills` pickup; bubblewrap availability in a container
- [ ] AC2 (`test_t030_ac2_*`): Non-interactive MCP tool call to a tiny test MCP server works with the narrowest setting (e.g. `default_tools_approval_mode`); never the bypass flag outside a container
- [ ] AC3 (`test_t030_ac3_*`): Tool-less extraction config proven: separate CODEX_HOME without mcp_servers (or `-c mcp_servers.cre.enabled=false`) shows no MCP tools
- [ ] AC4 (`test_t030_ac4_*`): LIBRARY_NOTES Codex [verify] items confirmed/corrected in this task; results summarized in PROGRESS.md
- [ ] AC5 (`test_t030_ac5_*`): Probe unit tests run offline with recorded probe outputs; live probe marked requires_codex
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/runner -q -k probe && uv run python scripts/check_task.py T030
```

## Done when
All ACs are met, verify exits 0, `passes` for T030 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
