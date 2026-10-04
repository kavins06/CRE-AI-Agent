# T033: CodexRunner, cre record, FakeRunner

> Product: an autonomous CRE acquisition analyst ("the Devin of real estate"). Follow the session protocol and branch model in `AGENTS.md` (work on `dev`).

| | |
|---|---|
| Milestone | M2: First working analyst (thin slice: SCREEN + UW_MODEL via cre run) |
| Depends on | T030, T031, T032 |
| Read first | SPEC §10.1, §10.7 |
| Allowed to modify | `src/cre_brain/runner/**`, `tests/runner/**`, `transcripts/**`, `PROGRESS.md`, `feature_list.json` (this task's `passes` only) |
| Must NOT modify | Anything else in `scripts/protected_paths.txt`; other tasks' entries; existing tests' assertions |
| Protected paths touched | No |

## Goal
Run analyst segments in the box container and record/replay them.

## Acceptance criteria
Each ACn needs at least one passing, non-skipped test named `test_t033_ac<n>_*`.
- [ ] AC1 (`test_t033_ac1_*`): CodexRunner runs `codex exec --json` in the box container with generated AGENTS.md + skills + `.codex/config.toml`; JSONL → AgentEvent; usage events
- [ ] AC2 (`test_t033_ac2_*`): Segments with caps (segment_max_min, turns, tokens); resume by session id
- [ ] AC3 (`test_t033_ac3_*`): `cre record` stores transcript + manifest (Codex version, raw/normalized hashes, release id); live test marked requires_codex
- [ ] AC4 (`test_t033_ac4_*`): FakeRunner loose-match replay asserting final state; CI uses recorded transcripts only (if none yet, a minimal transcript recorded by the spike)
- [ ] `make check` passes.

## Verify (must exit 0; paste the tail into PROGRESS.md)
```bash
uv run pytest tests/runner -q -k 'codex or fake' && uv run python scripts/check_task.py T033
```

## Done when
All ACs are met, verify exits 0, `passes` for T033 is true, the task branch is merged into `dev` and pushed, and a PROGRESS.md entry is written. If you are blocked, write a BLOCKED entry with evidence and move on.
